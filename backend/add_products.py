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
STORE_CURRENCY = os.getenv("MEDUSA_STORE_CURRENCY", "eur")
RECREATE_EXISTING_PRODUCTS = (
    os.getenv("RECREATE_EXISTING_PRODUCTS", "false").lower() == "true"
)


def make_variants(option_key, values, price=2999):
    amount = round(price / 100, 2)
    return [
        {
            "title": v,
            "options": {option_key: v},
            "prices": [{"amount": amount, "currency_code": STORE_CURRENCY}],
        }
        for v in values
    ]


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
    {
        "title": "Training Shorts",
        "description": "Lightweight four-way stretch training shorts with zip pocket and quick-dry lining. Great for gym sessions and summer runs.",
        "options": [{"title": "Size", "values": ["S", "M", "L", "XL"]}],
        "variants": make_variants("Size", ["S", "M", "L", "XL"], 2799),
    },
    {
        "title": "Sports Bra",
        "description": "Medium-support sports bra with breathable fabric and removable cups. Designed for running, HIIT and studio workouts.",
        "options": [{"title": "Size", "values": ["XS", "S", "M", "L"]}],
        "variants": make_variants("Size", ["XS", "S", "M", "L"], 3299),
    },
    {
        "title": "Jump Rope",
        "description": "Adjustable speed jump rope with smooth ball bearings and anti-slip handles. Ideal for cardio, conditioning and warm-ups.",
        "options": [{"title": "Color", "values": ["Black", "Red"]}],
        "variants": make_variants("Color", ["Black", "Red"], 1599),
    },
    {
        "title": "Protein Shaker Bottle",
        "description": "Leak-proof protein shaker bottle with mixing ball and measurement marks. Perfect for post-workout shakes and hydration.",
        "options": [{"title": "Size", "values": ["500ml", "700ml"]}],
        "variants": make_variants("Size", ["500ml", "700ml"], 1299),
    },
    {
        "title": "Smart Fitness Watch",
        "description": "GPS fitness watch with heart-rate tracking, sleep monitoring and workout modes for running, cycling and strength sessions.",
        "options": [{"title": "Color", "values": ["Black", "Silver"]}],
        "variants": make_variants("Color", ["Black", "Silver"], 12999),
    },
    {
        "title": "Lifting Gloves",
        "description": "Padded lifting gloves with wrist support and ventilated mesh panels. Helps improve grip during strength training.",
        "options": [{"title": "Size", "values": ["S", "M", "L"]}],
        "variants": make_variants("Size", ["S", "M", "L"], 1899),
    },
    {
        "title": "Massage Gun",
        "description": "Portable percussion massage gun with multiple heads and speed levels. Great for muscle recovery after hard workouts.",
        "options": [{"title": "Color", "values": ["Black"]}],
        "variants": make_variants("Color", ["Black"], 9999),
    },
    {
        "title": "Adjustable Dumbbell Set",
        "description": "Space-saving adjustable dumbbell set for progressive home strength training. Quick-change weight system for multiple exercises.",
        "options": [{"title": "Weight", "values": ["20kg Set", "30kg Set"]}],
        "variants": make_variants("Weight", ["20kg Set", "30kg Set"], 14999),
    },
    {
        "title": "Kettlebell 12kg",
        "description": "Powder-coated 12kg kettlebell with wide grip handle. Suitable for swings, squats, presses and functional fitness circuits.",
        "options": [{"title": "Weight", "values": ["12kg"]}],
        "variants": make_variants("Weight", ["12kg"], 4599),
    },
    {
        "title": "Adjustable Workout Bench",
        "description": "Foldable adjustable workout bench with incline and flat settings. Ideal for presses, rows and seated strength work at home.",
        "options": [{"title": "Style", "values": ["Adjustable Bench"]}],
        "variants": make_variants("Style", ["Adjustable Bench"], 11999),
    },
    {
        "title": "Running Belt",
        "description": "Slim running belt with secure phone pocket and reflective trim. Keeps essentials close without bouncing on long runs.",
        "options": [{"title": "Color", "values": ["Black", "Neon Yellow"]}],
        "variants": make_variants("Color", ["Black", "Neon Yellow"], 1799),
    },
    {
        "title": "Ankle Weights",
        "description": "Soft adjustable ankle weights for walking, toning and lower-body workouts. Comfortable fit with secure hook-and-loop closure.",
        "options": [{"title": "Weight", "values": ["1kg Pair", "2kg Pair"]}],
        "variants": make_variants("Weight", ["1kg Pair", "2kg Pair"], 2499),
    },
    {
        "title": "Pull-Up Bar",
        "description": "Doorway pull-up bar for upper-body training at home. Supports pull-ups, chin-ups and hanging core exercises.",
        "options": [{"title": "Style", "values": ["Doorway Bar"]}],
        "variants": make_variants("Style", ["Doorway Bar"], 3999),
    },
    {
        "title": "Balance Board",
        "description": "Wooden balance board for core stability, ankle strength and rehabilitation drills. Useful for surfers, runners and athletes.",
        "options": [{"title": "Color", "values": ["Natural Wood"]}],
        "variants": make_variants("Color", ["Natural Wood"], 3499),
    },
]

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # Get admin token
        print("Logging in...")
        auth = await client.post(
            f"{MEDUSA_URL}/auth/user/emailpass",
            json={"email": EMAIL, "password": PASSWORD}
        )
        token = auth.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Authenticated")

        existing_res = await client.get(
            f"{MEDUSA_URL}/admin/products",
            headers=headers,
            params={"limit": 100},
        )
        existing_res.raise_for_status()
        existing_products = {
            product["title"]: product
            for product in existing_res.json().get("products", [])
        }

        # Create each product
        for p in PRODUCTS:
            existing_product = existing_products.get(p["title"])
            if existing_product:
                if not RECREATE_EXISTING_PRODUCTS:
                    print(f"Skipped existing product: {p['title']}")
                    continue

                delete_res = await client.delete(
                    f"{MEDUSA_URL}/admin/products/{existing_product['id']}",
                    headers=headers,
                )
                if delete_res.status_code not in (200, 204):
                    print(
                        "Failed to delete existing product: "
                        f"{p['title']} - {delete_res.text[:100]}"
                    )
                    continue
                print(f"Deleted existing product: {p['title']}")

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
            if res.status_code in (200, 201):
                print(f"Created: {p['title']}")
            else:
                print(f"Failed: {p['title']} - {res.text[:100]}")

asyncio.run(main())
