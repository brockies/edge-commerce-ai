from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
import psycopg2
from sentence_transformers import SentenceTransformer
import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. Set it in backend/.env"
        )
    return value

app = FastAPI(title="Edge Commerce Brain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDUSA_URL = require_env("MEDUSA_URL")
OLLAMA_URL = require_env("OLLAMA_URL")
DEFAULT_MODEL = require_env("DEFAULT_MODEL")
EXPLANATION_PROVIDER = os.getenv("EXPLANATION_PROVIDER", "ollama").lower()
RECOMMENDATION_PROVIDER = os.getenv("RECOMMENDATION_PROVIDER", EXPLANATION_PROVIDER).lower()
EXPLANATION_MODEL = os.getenv("EXPLANATION_MODEL", "llama3.2:3b")
RECOMMENDATION_MODEL = os.getenv("RECOMMENDATION_MODEL", EXPLANATION_MODEL)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
DB_URL = require_env("DB_URL")
MEDUSA_PUBLISHABLE_KEY = require_env("MEDUSA_PUBLISHABLE_KEY")
HF_LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "true").lower() == "true"
DEFAULT_COUNTRY_CODE = os.getenv("MEDUSA_COUNTRY_CODE", "gb")
embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2",
    local_files_only=HF_LOCAL_ONLY,
)

class RecommendRequest(BaseModel):
    customer_query: str
    model: str = DEFAULT_MODEL
    mode: str = "fast"


def tokenize(text: str) -> set[str]:
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "your",
        "out",
        "into",
        "gear",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 2 and token not in stopwords
    }


def get_products_from_embeddings(limit: int = 50):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, description
        FROM product_embeddings
        ORDER BY title ASC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2] or "",
            "thumbnail": None,
        }
        for r in rows
    ]


async def get_products():
    if not MEDUSA_URL:
        return {
            "products": get_products_from_embeddings(),
            "source": "pgvector-fallback",
            "warning": "MEDUSA_URL is not set; returning embedded catalogue fallback",
        }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            region_response = await client.get(
                f"{MEDUSA_URL}/store/regions",
                headers={"x-publishable-api-key": MEDUSA_PUBLISHABLE_KEY},
            )
            region_response.raise_for_status()
            regions = region_response.json().get("regions", [])
            region = next(
                (
                    region
                    for region in regions
                    if any(
                        country.get("iso_2") == DEFAULT_COUNTRY_CODE
                        for country in region.get("countries", [])
                    )
                ),
                regions[0] if regions else None,
            )
            region_id = region.get("id") if region else None
            currency_code = region.get("currency_code") if region else None

            response = await client.get(
                f"{MEDUSA_URL}/store/products",
                headers={"x-publishable-api-key": MEDUSA_PUBLISHABLE_KEY},
                params={
                    "region_id": region_id,
                    "fields": "*variants.calculated_price,+variants.options,+options,+thumbnail,+title,+description",
                } if region_id else None,
            )
            response.raise_for_status()
            payload = response.json()
            products = payload.get("products", [])
            return {
                "products": products,
                "source": "medusa",
                "currency_code": currency_code,
                "country_code": DEFAULT_COUNTRY_CODE,
                "region_id": region_id,
            }
    except Exception as exc:
        try:
            fallback = get_products_from_embeddings()
            return {
                "products": fallback,
                "source": "pgvector-fallback",
                "warning": f"Medusa unavailable: {str(exc)}",
            }
        except Exception as fallback_exc:
            return {
                "products": [],
                "source": "empty-fallback",
                "warning": (
                    "Medusa and pgvector fallback unavailable: "
                    f"medusa_error={str(exc)}; fallback_error={str(fallback_exc)}"
                ),
            }

def get_relevant_products(query: str, top_k: int = 5):
    query_embedding = embedding_model.encode(query).tolist()
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, description
        FROM product_embeddings
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """, (json.dumps(query_embedding), top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "title": r[1], "description": r[2]} for r in rows]


def build_reason(query: str, product: dict) -> str:
    query_tokens = tokenize(query)
    product_text = f'{product.get("title", "")} {product.get("description", "")}'
    product_tokens = tokenize(product_text)
    matching_tokens = sorted(query_tokens.intersection(product_tokens))

    if matching_tokens:
        top_matches = ", ".join(matching_tokens[:2])
        return f"Strong match for {top_matches}."

    title = product.get("title", "This product")
    return f"{title} is a close fit for this request."


def build_fast_trace() -> list[str]:
    return [
        "Converted the shopper request into a local embedding vector.",
        "Compared that vector against product embeddings stored in pgvector.",
        "Returned the nearest catalogue matches, then asked the configured model to summarise them.",
    ]


def build_deep_trace() -> list[str]:
    return [
        "Converted the shopper request into a local embedding vector.",
        "Retrieved the nearest catalogue candidates from pgvector.",
        "Asked the configured model to choose the final set and explain the tradeoffs.",
    ]


def resolve_provider_label(provider: str) -> str:
    if provider == "openai":
        return "openai"
    return "ollama"


def build_insight_prompt(query: str, recommendations: list[dict]) -> str:
    recommendation_lines = "\n".join(
        [
            f'- {item["title"]}: {item["reason"]}'
            for item in recommendations
        ]
    )
    return f"""You are a shopping assistant.

Customer request: {query}

Recommended products:
{recommendation_lines}

Return only valid JSON with this shape:
{{
  "insight": "3 short sentences explaining why this set works",
  "trace": [
    "short decision step",
    "short decision step",
    "short decision step"
  ]
}}

Rules:
- Keep `insight` to 3 short sentences.
- Mention the shopper goal and the overall product mix.
- Mention one useful tradeoff or tip.
- Keep each `trace` step short and clear for a business audience.
- Do not include markdown or any text outside the JSON object."""


def build_llm_recommendation_prompt(query: str, products: list[dict]) -> str:
    product_lines = "\n".join(
        [
            f'- {{"id": "{p["id"]}", "title": "{p["title"]}", "description": {json.dumps(p.get("description", ""))}}}'
            for p in products
        ]
    )
    return f"""You are an ecommerce recommendation assistant.

Customer request: {query}

Available products:
{product_lines}

Return only valid JSON with this exact shape:
{{
  "recommendations": [
    {{
      "id": "exact product id from available products",
      "title": "exact product title from available products",
      "reason": "short shopper-friendly reason"
    }}
  ],
  "insight": "3 short sentences explaining why this set works"
}}

Rules:
- Recommend exactly 4 unique products from the available products list.
- Use exact ids and exact titles from the available products list.
- Keep each reason short.
- Keep insight concise and natural.
- Do not include markdown or any text outside the JSON object."""


def extract_json_object(value: str) -> str | None:
    start = value.find("{")
    end = value.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return value[start : end + 1]


def extract_openai_content(payload: dict) -> str:
    choices = payload.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif "text" in item:
                    text_parts.append(str(item.get("text", "")))
        return "".join(text_parts)

    return str(content)


async def generate_json_response(provider: str, model: str, prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        if provider == "openai":
            if not OPENAI_API_KEY:
                raise RuntimeError(
                    "OPENAI_API_KEY is required when using provider=openai."
                )

            response = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
            response_text = extract_openai_content(payload)
        else:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "think": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            response_text = payload.get("response", "")

        parsed_text = extract_json_object(response_text) or response_text
        return json.loads(parsed_text)


async def generate_explanation(query: str, recommendations: list[dict]) -> dict:
    parsed = await generate_json_response(
        EXPLANATION_PROVIDER,
        EXPLANATION_MODEL,
        build_insight_prompt(query, recommendations),
    )
    return {
        "insight": parsed.get("insight", ""),
        "trace": parsed.get("trace", [])[:3],
    }


async def generate_ranked_recommendations(query: str, products: list[dict]) -> dict:
    parsed = await generate_json_response(
        RECOMMENDATION_PROVIDER,
        RECOMMENDATION_MODEL,
        build_llm_recommendation_prompt(query, products),
    )
    return {
        "recommendations": parsed.get("recommendations", [])[:4],
        "insight": parsed.get("insight", ""),
    }


def execution_pattern() -> str:
    if EXPLANATION_PROVIDER == "ollama" and RECOMMENDATION_PROVIDER == "ollama":
        return "local-only"
    if EXPLANATION_PROVIDER == "openai" or RECOMMENDATION_PROVIDER == "openai":
        return "tiered"
    return "mixed"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "execution_pattern": execution_pattern(),
        "retrieval": {
            "provider": "local",
            "embeddings_model": "all-MiniLM-L6-v2",
            "vector_store": "pgvector",
        },
        "explanation": {
            "provider": resolve_provider_label(EXPLANATION_PROVIDER),
            "model": EXPLANATION_MODEL,
        },
        "recommendation": {
            "provider": resolve_provider_label(RECOMMENDATION_PROVIDER),
            "model": RECOMMENDATION_MODEL,
        },
    }


@app.get("/products")
async def products():
    return await get_products()


@app.post("/recommend")
async def recommend(req: RecommendRequest):
    products = get_relevant_products(req.customer_query, top_k=8)
    unique_products = []
    seen_ids = set()

    for product in products:
        product_id = product["id"]
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        unique_products.append(product)
        if len(unique_products) == 4:
            break

    recommendations = [
        {
            "id": product["id"],
            "title": product["title"],
            "reason": build_reason(req.customer_query, product),
        }
        for product in unique_products
    ]

    async def stream_response():
        if req.mode == "deep":
            try:
                llm_payload = await generate_ranked_recommendations(
                    req.customer_query, unique_products
                )
                llm_recommendations = llm_payload.get("recommendations", [])[:4]

                yield (
                    f"data: {json.dumps({'type': 'recommendations', 'response': json.dumps({'recommendations': llm_recommendations}), 'done': False})}\n\n"
                )

                explanation = await generate_explanation(
                    req.customer_query, llm_recommendations
                )

                if explanation.get("trace"):
                    yield (
                        f"data: {json.dumps({'type': 'trace', 'trace': explanation['trace'], 'done': False})}\n\n"
                    )

                if explanation.get("insight"):
                    yield (
                        f"data: {json.dumps({'type': 'insight', 'response': explanation['insight'], 'done': False})}\n\n"
                    )
            except Exception:
                yield (
                    f"data: {json.dumps({'type': 'recommendations', 'response': json.dumps({'recommendations': recommendations}), 'done': False})}\n\n"
                )
                fallback_insight = (
                    "The deep AI mode could not complete, so these vector-search matches "
                    "were returned instead."
                )
                fallback_trace = build_deep_trace()
                yield (
                    f"data: {json.dumps({'type': 'trace', 'trace': fallback_trace, 'done': False})}\n\n"
                )
                yield (
                    f"data: {json.dumps({'type': 'insight', 'response': fallback_insight, 'done': False})}\n\n"
                )

            yield f"data: {json.dumps({'type': 'done', 'done': True})}\n\n"
            return

        payload = {
            "type": "recommendations",
            "response": json.dumps({"recommendations": recommendations}),
            "done": False,
        }
        yield f"data: {json.dumps(payload)}\n\n"
        yield (
            f"data: {json.dumps({'type': 'trace', 'trace': build_fast_trace(), 'done': False})}\n\n"
        )

        try:
            explanation = await generate_explanation(
                req.customer_query, recommendations
            )
            if explanation.get("insight"):
                yield (
                    f"data: {json.dumps({'type': 'insight', 'response': explanation['insight'], 'done': False})}\n\n"
                )
        except Exception:
            fallback_insight = (
                "These products were matched locally using the shopper request and "
                "catalogue similarity, then summarised by the configured inference tier."
            )
            yield (
                f"data: {json.dumps({'type': 'insight', 'response': fallback_insight, 'done': False})}\n\n"
            )

        yield f"data: {json.dumps({'type': 'done', 'done': True})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream"
    )


@app.post("/search")
async def search(req: RecommendRequest):
    products = get_relevant_products(req.customer_query, top_k=5)
    return {"query": req.customer_query, "matched_products": products}
