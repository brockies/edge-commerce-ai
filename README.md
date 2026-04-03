# ActiveEdge AI - Edge Commerce Intelligence

> Medusa-backed shopping demo with local semantic search and a configurable inference tier for explanation and ranking.

## What This Demo Does

ActiveEdge AI is a local-first commerce assistant for fitness products.

A shopper enters a prompt such as `I want to start running outdoors`, and the app:

1. Embeds the query locally with `all-MiniLM-L6-v2`
2. Finds the nearest products in `pgvector`
3. Uses the configured inference tier to explain or rank those candidates
4. Shows Medusa product cards with real prices, variants, and add-to-cart

The demo currently supports two recommendation modes:

- `Fast`: pgvector picks the products immediately, then the configured explanation tier explains the choices
- `Deep AI`: the configured ranking tier is put back in the recommendation loop to choose the final set from vector-search candidates

Both modes keep retrieval on the machine.

The current codebase also supports a tiered inference pattern:

- retrieval stays local
- explanation and deep-mode ranking can run either on-device via Ollama or via a configured fallback provider

## Current Stack

| Layer                       | Technology                                          |
| --------------------------- | --------------------------------------------------- |
| Ecommerce                   | Medusa v2 (standalone service)                      |
| Product API                 | Medusa Store API                                    |
| Backend                     | FastAPI                                             |
| Frontend                    | React + TypeScript                                  |
| Vector Search               | PostgreSQL + pgvector                               |
| Embeddings                  | sentence-transformers (`all-MiniLM-L6-v2`)          |
| Local inference             | Ollama                                              |
| Optional fallback inference | OpenAI API                                          |
| Current demo model defaults | `llama3.2:3b` for explanation and deep-mode ranking |
| Optional heavier model      | `deepseek-r1:7b`                                    |

## How Search Works

### Fast mode

1. The backend embeds the shopper query locally
2. pgvector returns the nearest catalogue matches
3. The backend returns 4 unique recommendations
4. The frontend maps recommendation IDs back to Medusa products
5. The configured explanation tier generates:
   - `How the AI Decided`
   - `Why These Picks`

### Deep AI mode

1. The backend embeds the shopper query locally
2. pgvector returns candidate products
3. The configured ranking tier chooses the final recommendation set from those candidates
4. The configured explanation tier generates the explanation and decision trace

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

## Tiered Inference Pattern

This app now supports a more realistic edge pattern:

- device tier: frontend, embeddings, pgvector retrieval, and Medusa integration
- inference tier: Ollama on the same machine for true on-device demos
- fallback tier: a configured provider for explanation and deep ranking when the endpoint device is underpowered

That means the app can preserve local retrieval while moving the heavier reasoning step to a more capable inference target when needed.

## Inference Decision Policy

The intended policy is:

- keep retrieval on the device by default
- choose the inference tier based on task complexity, latency budget, and device capability

Use edge inference when:

- the task is lightweight
- the device can stay within the target response time
- privacy or low-egress requirements are highest
- the request is a fast-path recommendation and local inference is acceptable

Escalate to a stronger inference tier when:

- the endpoint device is too slow for the requested experience
- the task needs deeper reasoning or ranking
- the user explicitly requests a richer advisory mode
- local inference exceeds the latency budget

In practical terms:

- `Fast` mode can keep retrieval on edge and use either local or fallback explanation
- `Deep AI` mode can keep retrieval on edge while moving final ranking to a stronger inference tier on constrained hardware

Architecture summary:

- edge-first retrieval
- policy-based inference escalation

## UI Experience

The current UI shows:

- fast or deep recommendation mode toggle
- recommended product cards
- real Medusa pricing and variants
- `How the AI Decided` trace
- `Why These Picks` explanation
- add-to-cart from recommendation cards

## Prerequisites

- Docker Desktop
- Node.js 20+
- Python 3.10+
- Ollama installed locally
- A standalone Medusa v2 project running separately
- Git Bash or another terminal you will use for the demo

For the Medusa setup used by this repo, see [docs/medusa-standalone-setup.md](docs/medusa-standalone-setup.md) and [scripts/bootstrap-standalone-medusa.ps1](scripts/bootstrap-standalone-medusa.ps1).

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
  -e POSTGRES_USER=<pgvector_user> \
  -e POSTGRES_PASSWORD=<pgvector_password> \
  -e POSTGRES_DB=<pgvector_database> \
  -p 5434:5432 \
  -d pgvector/pgvector:pg16
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
```

Create `backend/.env` from [backend/.env.example](backend/.env.example).

Minimum values:

Never commit real credentials or API keys.

```env
MEDUSA_URL=http://127.0.0.1:9000
MEDUSA_PUBLISHABLE_KEY=pk_your_publishable_key_here
MEDUSA_ADMIN_EMAIL=admin@example.com
MEDUSA_ADMIN_PASSWORD=<your_medusa_admin_password>
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_MODEL=deepseek-r1:7b
DB_URL=postgresql://<user>:<password>@127.0.0.1:5434/<database>
HF_LOCAL_ONLY=true
```

Optional model overrides:

```env
EXPLANATION_MODEL=llama3.2:3b
RECOMMENDATION_MODEL=llama3.2:3b
MEDUSA_COUNTRY_CODE=gb
```

Optional provider overrides:

```env
EXPLANATION_PROVIDER=ollama
RECOMMENDATION_PROVIDER=ollama
OPENAI_API_KEY=<your_openai_api_key>
OPENAI_BASE_URL=https://api.openai.com/v1
```

Example demo fallback configuration:

```env
EXPLANATION_PROVIDER=openai
RECOMMENDATION_PROVIDER=openai
EXPLANATION_MODEL=gpt-5.4-mini
RECOMMENDATION_MODEL=gpt-5.4-mini
OPENAI_API_KEY=<your_openai_api_key>
```

### 3. Embed the catalog

```bash
cd backend
python embed_products.py
```

### 4. Start the backend

```bash
cd backend
source venv/Scripts/activate
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

### Step 1: Start Docker Desktop

Wait for Docker Desktop to finish starting before moving on.

### Step 2: Start Medusa

From the standalone Medusa project:

```bash
cd <path-to-medusa>
npm run dev
```

The Medusa server should then be available on `http://127.0.0.1:9000`.

### Step 3: Start Ollama

If you are using local inference, make sure Ollama is running, then check the installed models:

```bash
ollama list
```

Confirm `llama3.2:3b` is available before continuing.

If you are using a fallback provider for explanation and deep ranking, this step is optional.

### Step 4: Start the databases

If the container already exists:

```bash
docker start medusa-postgres
docker start edge-commerce-db
```

If you have not created it yet, use the database setup command earlier in this README.

### Step 5: Start the backend

```bash
cd backend
source venv/Scripts/activate
uvicorn main:app --reload --port 8000
```

### Step 6: Start the frontend

```bash
cd frontend
npm start
```

### Step 7: Open the app

- Frontend: `http://localhost:3000`
- Backend health: `http://127.0.0.1:8000/health`
- Medusa: `http://127.0.0.1:9000`

### Step 8: Demo checklist

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

If you are setting up Medusa on a new machine, use [docs/medusa-standalone-setup.md](docs/medusa-standalone-setup.md).

## API Endpoints

| Method | Endpoint     | Description                                      |
| ------ | ------------ | ------------------------------------------------ |
| GET    | `/health`    | Health check and configured default model        |
| GET    | `/products`  | Fetch products from Medusa with pricing/variants |
| POST   | `/search`    | Debug endpoint for vector-search matches         |
| POST   | `/recommend` | Streaming SSE recommendation endpoint            |

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

`/health` also returns the configured inference pattern plus the explanation and recommendation providers/models.

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
- configurable inference tier for explanation and ranking
- ecommerce catalog and pricing from Medusa
- optional cloud fallback for underpowered devices

That gives you a cleaner edge-AI story: keep retrieval on the device, then choose the right inference target for the hardware envelope.

## Roadmap

- real Medusa cart persistence and checkout
- richer metadata filters for activity, budget, and weather
- hybrid retrieval plus AI refinement
- startup scripts for the full local stack
- deployment packaging for demos

## Built For

This project is designed as a stakeholder-friendly demo of edge commerce AI: fast local retrieval, visible local reasoning, and real product data from Medusa.
