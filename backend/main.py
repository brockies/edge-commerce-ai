from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx
import json
import psycopg2
from sentence_transformers import SentenceTransformer
import os
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
DB_URL = require_env("DB_URL")
MEDUSA_PUBLISHABLE_KEY = require_env("MEDUSA_PUBLISHABLE_KEY")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class RecommendRequest(BaseModel):
    customer_query: str
    model: str = DEFAULT_MODEL


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
            response = await client.get(
                f"{MEDUSA_URL}/store/products",
                headers={"x-publishable-api-key": MEDUSA_PUBLISHABLE_KEY},
            )
            response.raise_for_status()
            payload = response.json()
            products = payload.get("products", [])
            return {
                "products": products,
                "source": "medusa",
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
        SELECT title, description
        FROM product_embeddings
        ORDER BY embedding <-> %s::vector
        LIMIT %s
    """, (json.dumps(query_embedding), top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"title": r[0], "description": r[1]} for r in rows]

@app.get("/health")
async def health():
    return {"status": "ok", "model": DEFAULT_MODEL}

@app.get("/products")
async def products():
    return await get_products()

@app.post("/recommend")
async def recommend(req: RecommendRequest):
    products = get_relevant_products(req.customer_query, top_k=5)

    product_list = "\n".join([
        f"- {p['title']}: {p.get('description', 'No description')}"
        for p in products
    ])

    prompt = f"""You are a helpful ecommerce product recommendation assistant.

Here are the available products:
{product_list}

Customer query: {req.customer_query}

Think through this carefully and recommend the most relevant products with reasons why."""

    async def stream_response():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": req.model,
                    "prompt": prompt,
                    "stream": True
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        yield f"data: {line}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream"
    )

@app.post("/search")
async def search(req: RecommendRequest):
    products = get_relevant_products(req.customer_query, top_k=5)
    return {"query": req.customer_query, "matched_products": products}