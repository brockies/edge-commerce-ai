import os
import httpx
import psycopg2
from sentence_transformers import SentenceTransformer
import json
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

MEDUSA_URL = os.getenv("MEDUSA_URL", "http://127.0.0.1:9000")
PUBLISHABLE_KEY = require_env("MEDUSA_PUBLISHABLE_KEY")
DB_URL = require_env("DB_URL")

print("🤖 Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Model loaded")

# Fetch products from Medusa
print("🛍️ Fetching products from Medusa...")
res = httpx.get(
    f"{MEDUSA_URL}/store/products?limit=100",
    headers={"x-publishable-api-key": PUBLISHABLE_KEY}
)
products = res.json()["products"]
print(f"✅ Found {len(products)} products")

# Connect to pgvector
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Embed and store each product
for p in products:
    title = p["title"]
    description = p.get("description") or ""
    text = f"{title}. {description}"
    
    embedding = model.encode(text).tolist()
    
    cur.execute("""
        INSERT INTO product_embeddings (id, title, description, embedding)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            description = EXCLUDED.description,
            embedding = EXCLUDED.embedding
    """, (p["id"], title, description, json.dumps(embedding)))
    
    print(f"✅ Embedded: {title}")

conn.commit()
cur.close()
conn.close()
print("\n🎉 All products embedded and stored in pgvector!")