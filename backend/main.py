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
EXPLANATION_MODEL = os.getenv("EXPLANATION_MODEL", "llama3.2:3b")
RECOMMENDATION_MODEL = os.getenv("RECOMMENDATION_MODEL", EXPLANATION_MODEL)
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


def build_insight_prompt(query: str, recommendations: list[dict]) -> str:
    recommendation_lines = "\n".join(
        [
            f'- {item["title"]}: {item["reason"]}'
            for item in recommendations
        ]
    )
    return f"""You are an on-device shopping assistant.

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
    return f"""You are a local ecommerce recommendation assistant.

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


async def generate_local_explanation(query: str, recommendations: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": EXPLANATION_MODEL,
                "prompt": build_insight_prompt(query, recommendations),
                "stream": False,
                "format": "json",
                "think": False,
            },
        )
        response.raise_for_status()
        payload = response.json()
        response_text = payload.get("response", "")
        parsed_text = extract_json_object(response_text) or response_text
        parsed = json.loads(parsed_text)
        return {
            "insight": parsed.get("insight", ""),
            "trace": parsed.get("trace", [])[:3],
        }

@app.get("/health")
async def health():
    return {"status": "ok", "model": DEFAULT_MODEL}

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
            response_text = ""
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{OLLAMA_URL}/api/generate",
                        json={
                            "model": RECOMMENDATION_MODEL,
                            "prompt": build_llm_recommendation_prompt(
                                req.customer_query, unique_products
                            ),
                            "stream": True,
                            "format": "json",
                            "think": False,
                        },
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            chunk = json.loads(line)
                            token = chunk.get("response", "")
                            if token:
                                response_text += token

                parsed_text = extract_json_object(response_text) or response_text
                parsed = json.loads(parsed_text)
                llm_recommendations = parsed.get("recommendations", [])[:4]

                yield (
                    f"data: {json.dumps({'type': 'recommendations', 'response': json.dumps({'recommendations': llm_recommendations}), 'done': False})}\n\n"
                )

                explanation = await generate_local_explanation(
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
                    "The deep AI mode could not complete, so these local vector matches "
                    "were returned instead."
                )
                fallback_trace = [
                    "Started from the shopper request.",
                    "Matched the closest local catalogue items.",
                    "Returned the fallback set to keep the demo responsive.",
                ]
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

        try:
            explanation = await generate_local_explanation(
                req.customer_query, recommendations
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
            fallback_insight = (
                "These products were matched locally using the shopper request and "
                "catalogue similarity, then summarised on-device for a faster demo."
            )
            fallback_trace = [
                "Read the shopper request locally.",
                "Pulled the nearest catalogue matches from pgvector.",
                "Asked the local model to summarise the fit.",
            ]
            yield (
                f"data: {json.dumps({'type': 'trace', 'trace': fallback_trace, 'done': False})}\n\n"
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
