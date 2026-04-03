# ActiveEdge AI - Edge Commerce Intelligence

> Medusa-backed shopping demo with local semantic search, local LLM reasoning, and zero data egress.

## What This Demo Does

ActiveEdge AI is a local-first commerce assistant for fitness products.

A shopper enters a prompt such as `I want to start running outdoors`, and the app:

1. Embeds the query locally with `all-MiniLM-L6-v2`
2. Finds the nearest products in `pgvector`
3. Uses a local Ollama model to explain or rank those candidates
4. Shows Medusa product cards with real prices, variants, and add-to-cart

The demo currently supports two recommendation modes:

- `Fast`: pgvector picks the products immediately, then a local LLM explains the choices
- `Deep AI`: a local LLM is put back in the recommendation loop to choose the final set from vector-search candidates

Both modes run locally on the machine.

## Current Stack

| Layer | Technology |
|---|---|
| Ecommerce | Medusa v2 (standalone service) |
| Product API | Medusa Store API |
| Backend | FastAPI |
| Frontend | React + TypeScript |
| Vector Search | PostgreSQL + pgvector |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) |
| Local LLM | Ollama |
| Current demo model defaults | `llama3.2:3b` for explanation and deep-mode ranking |
| Optional heavier model | `deepseek-r1:7b` |

## How Search Works

### Fast mode

1. The backend embeds the shopper query locally
2. pgvector returns the nearest catalogue matches
3. The backend returns 4 unique recommendations
4. The frontend maps recommendation IDs back to Medusa products
5. `llama3.2:3b` generates:
   - `How the AI Decided`
   - `Why These Picks`

### Deep AI mode

1. The backend embeds the shopper query locally
2. pgvector returns candidate products
3. `llama3.2:3b` chooses the final recommendation set from those candidates
4. The same model generates the explanation and decision trace

## Why RAG?

Instead of sending the full catalog to a model, we:

- embed each product locally with `all-MiniLM-L6-v2`
- embed the shopper query locally at request time
- use `pgvector` to retrieve the most relevant products
- pass only those retrieved candidates into the AI step when needed

Why that matters:

- it scales much better than sending the whole catalog to the model
- it keeps responses faster and more grounded in real products
- it reduces local inference cost
- it works for both `Fast` and `Deep AI` modes

In the current implementation, retrieval is performed before the LLM step in both modes.

## UI Experience

The current UI shows:

- fast or deep recommendation mode toggle
- recommended product cards
- real Medusa pricing and variants
- local `How the AI Decided` trace
- local `Why These Picks` explanation
- add-to-cart from recommendation cards

## Prerequisites

- Docker Desktop
- Node.js 20+
- Python 3.10+
- Ollama installed locally
- A standalone Medusa v2 project running separately

For the Medusa setup used by this repo, see [docs/medusa-standalone-setup.md](/C:/Users/s.brockie/projects/edge-commerce-ai/docs/medusa-standalone-setup.md) and [scripts/bootstrap-standalone-medusa.ps1](/C:/Users/s.brockie/projects/edge-commerce-ai/scripts/bootstrap-standalone-medusa.ps1).

## Recommended Local Models

For this laptop-friendly demo flow:

```bash
ollama pull llama3.2:3b
```

Optional heavier reasoning model:

```bash
ollama pull deepseek-r1:7b
```

## Getting Started

### 1. Start the pgvector database

```bash
docker run --name edge-commerce-db \
  -e POSTGRES_USER=medusa-store \
  -e POSTGRES_PASSWORD=medusa-store \
  -e POSTGRES_DB=medusa-store \
  -p 5434:5432 \
  -d pgvector/pgvector:pg16
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `backend/.env` from [backend/.env.example](/C:/Users/s.brockie/projects/edge-commerce-ai/backend/.env.example).

Minimum values:

```env
MEDUSA_URL=http://127.0.0.1:9000
MEDUSA_PUBLISHABLE_KEY=pk_your_publishable_key_here
MEDUSA_ADMIN_EMAIL=admin@example.com
MEDUSA_ADMIN_PASSWORD=supersecret
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_MODEL=deepseek-r1:7b
DB_URL=postgresql://medusa-store:medusa-store@127.0.0.1:5434/medusa-store
HF_LOCAL_ONLY=true
```

Optional model overrides:

```env
EXPLANATION_MODEL=llama3.2:3b
RECOMMENDATION_MODEL=llama3.2:3b
MEDUSA_COUNTRY_CODE=gb
```

### 3. Embed the catalog

```bash
cd backend
python embed_products.py
```

### 4. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000`.

## Run The Demo

If the machine is already set up, use this startup order before a demo:

### 1. Start Medusa

Make sure the standalone Medusa server is running on `http://127.0.0.1:9000`.

### 2. Start Ollama

Make sure Ollama is running and the demo model is available:

```bash
ollama list
```

Expected model for the current demo flow:

```bash
llama3.2:3b
```

### 3. Start the pgvector database

If the container already exists:

```bash
docker start edge-commerce-db
```

If you have not created it yet, use the database setup command in [README.md](/C:/Users/s.brockie/projects/edge-commerce-ai/README.md#L108).

### 4. Start the backend

```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

### 5. Start the frontend

```bash
cd frontend
npm start
```

### 6. Open the app

- Frontend: `http://localhost:3000`
- Backend health: `http://127.0.0.1:8000/health`
- Medusa: `http://127.0.0.1:9000`

### 7. Demo checklist

Before presenting, verify:

- Medusa products load in the UI
- recommendation mode toggle is visible
- `Why These Picks` appears after a search
- `How the AI Decided` appears after a search
- add-to-cart works from recommendation cards

## Medusa Notes

This repo expects Medusa to run separately from the frontend/backend demo.

The current implementation uses Medusa for:

- product catalog
- publishable Store API access
- region-aware pricing
- variants used by the cart UI

If you are setting up Medusa on a new machine, use [docs/medusa-standalone-setup.md](/C:/Users/s.brockie/projects/edge-commerce-ai/docs/medusa-standalone-setup.md).

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check and configured default model |
| GET | `/products` | Fetch products from Medusa with pricing/variants |
| POST | `/search` | Debug endpoint for vector-search matches |
| POST | `/recommend` | Streaming SSE recommendation endpoint |

`/recommend` accepts:

```json
{
  "customer_query": "I want gear for outdoor running",
  "mode": "fast"
}
```

Supported modes:

- `fast`
- `deep`

`/recommend` streams event types in this order:

- `recommendations`
- `trace`
- `insight`
- `done`

## Project Structure

```text
edge-commerce-ai/
|-- backend/
|   |-- .env.example
|   |-- add_products.py
|   |-- embed_products.py
|   |-- main.py
|   `-- requirements.txt
|-- docs/
|   `-- medusa-standalone-setup.md
|-- frontend/
|   `-- src/
|       |-- App.css
|       `-- App.tsx
`-- scripts/
    `-- bootstrap-standalone-medusa.ps1
```

## Current Demo Positioning

This is best framed as:

- semantic retrieval running locally
- AI reasoning running locally
- ecommerce catalog and pricing from Medusa
- no cloud inference required

That gives you a clean edge-AI story without blocking the UI on a slower model for every request.

## Roadmap

- real Medusa cart persistence and checkout
- richer metadata filters for activity, budget, and weather
- hybrid retrieval plus AI refinement
- startup scripts for the full local stack
- deployment packaging for demos

## Built For

This project is designed as a stakeholder-friendly demo of edge commerce AI: fast local retrieval, visible local reasoning, and real product data from Medusa.
