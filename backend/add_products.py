import os
import httpx
import asyncio
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
EMAIL = require_env("MEDUSA_ADMIN_EMAIL")
PASSWORD = require_env("MEDUSA_ADMIN_PASSWORD")


def make_variants(option_key, values, price=2999):
    return [{"title": v, "options": {option_key: v}, "prices": [{"amount": price, "currency_code": "usd"}]} for v in values]


PRODUCTS = [
    {
        "title": "Running Jacket",
        "description": "Lightweight breathable running jacket with reflective strips. Perfect for outdoor running in all weather.",
        "options": [{"title": "Size", "values": ["S", "M", "L", "XL"]}],
        "variants": make_variants("Size", ["S", "M", "L", "XL"]),
    },
    {
        "title": "Running Shoes",
        "description": "High-performance running shoes with cushioned sole and breathable mesh upper. Great for road and trail running.",
        "options": [{"title": "Size", "values": ["40", "41", "42", "43", "44"]}],
        "variants": make_variants("Size", ["40", "41", "42", "43", "44"], 8999),
    },
    {
        "title": "Yoga Mat",
        "description": "Extra thick non-slip yoga mat with alignment lines. Ideal for yoga, pilates and home workouts.",
        "options": [{"title": "Color", "values": ["Purple", "Blue", "Black"]}],
        "variants": make_variants("Color", ["Purple", "Blue", "Black"], 3999),
    },
    {
        "title": "Sports Water Bottle",
        "description": "Insulated stainless steel water bottle that keeps drinks cold for 24 hours. BPA free with leak-proof lid.",
        "options": [{"title": "Size", "values": ["500ml", "750ml", "1L"]}],
        "variants": make_variants("Size", ["500ml", "750ml", "1L"], 1999),
    },
    {
        "title": "Wireless Earbuds",
        "description": "Sport wireless earbuds with secure fit ear hooks. Sweat resistant with 8 hour battery life. Perfect for workouts.",
        "options": [{"title": "Color", "values": ["White", "Black"]}],
        "variants": make_variants("Color", ["White", "Black"], 7999),
    },
    {
        "title": "Gym Backpack",
        "description": "Durable gym backpack with separate shoe compartment and wet pocket. 30L capacity with laptop sleeve.",
        "options": [{"title": "Color", "values": ["Black", "Grey", "Navy"]}],
        "variants": make_variants("Color", ["Black", "Grey", "Navy"], 4999),
    },
    {
        "title": "Compression Leggings",
        "description": "High-waist compression leggings with moisture-wicking fabric. Ideal for running, gym and everyday wear.",
        "options": [{"title": "Size", "values": ["XS", "S", "M", "L", "XL"]}],
        "variants": make_variants("Size", ["XS", "S", "M", "L", "XL"], 3499),
    },
    {
        "title": "Foam Roller",
        "description": "High-density foam roller for muscle recovery and myofascial release. Suitable for all fitness levels.",
        "options": [{"title": "Size", "values": ["Short", "Standard", "Long"]}],
        "variants": make_variants("Size", ["Short", "Standard", "Long"], 2499),
    },
    {
        "title": "Sports Socks 3 Pack",
        "description": "Cushioned ankle sports socks with arch support and moisture-wicking material. Pack of 3 pairs.",
        "options": [{"title": "Size", "values": ["S", "M", "L"]}],
        "variants": make_variants("Size", ["S", "M", "L"], 999),
    },
    {
        "title": "Resistance Bands Set",
        "description": "Set of 5 resistance bands with varying tension levels. Great for strength training, rehab and stretching.",
        "options": [{"title": "Pack", "values": ["5 Band Set"]}],
        "variants": make_variants("Pack", ["5 Band Set"], 1499),
    },
    {
        "title": "Sports Cap",
        "description": "Lightweight performance cap with UV protection and moisture-wicking sweatband. Adjustable fit.",
        "options": [{"title": "Color", "values": ["Black", "White", "Navy"]}],
        "variants": make_variants("Color", ["Black", "White", "Navy"], 1299),
    },
    {
        "title": "Hoodie",
        "description": "Heavyweight cotton fleece hoodie with kangaroo pocket. A wardrobe staple for post-workout comfort.",
        "options": [{"title": "Size", "values": ["S", "M", "L", "XL"]}],
        "variants": make_variants("Size", ["S", "M", "L", "XL"], 5999),
    },
]

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # Get admin token
        print("🔐 Logging in...")
        auth = await client.post(
            f"{MEDUSA_URL}/auth/user/emailpass",
            json={"email": EMAIL, "password": PASSWORD}
        )
        token = auth.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Authenticated")

        # Create each product
        for p in PRODUCTS:
            payload = {
                "title": p["title"],
                "description": p["description"],
                "status": "published",
                "options": p["options"],
                "variants": p["variants"],
            }
            if "thumbnail" in p:
                payload["thumbnail"] = p["thumbnail"]

            res = await client.post(
                f"{MEDUSA_URL}/admin/products",
                json=payload,
                headers=headers
            )
            if res.status_code == 200:
                print(f"✅ Created: {p['title']}")
            else:
                print(f"❌ Failed: {p['title']} — {res.text[:100]}")

asyncio.run(main())