# ActiveEdge AI — Edge Commerce Intelligence

> On-device AI product recommendation engine built with RAG architecture, DeepSeek-R1 7B, pgvector semantic search, FastAPI and React. Zero data egress. Full reasoning transparency.

![ActiveEdge AI Demo](https://img.shields.io/badge/AI-DeepSeek--R1%207B-blue) ![Stack](https://img.shields.io/badge/Stack-FastAPI%20%7C%20React%20%7C%20pgvector-green) ![Data](https://img.shields.io/badge/Data%20Egress-Zero-brightgreen)

---

## What Is This?

ActiveEdge AI is a proof-of-concept demonstrating **Reasoning at the Edge** — a 2026 AI trend where small, capable models run entirely on-device rather than in the cloud.

A customer types a natural language query like *"I want to start running outdoors"* and the system:

1. Converts the query to a vector embedding **locally**
2. Runs a semantic similarity search against the product catalogue via **pgvector**
3. Sends only the most relevant products to **DeepSeek-R1 7B** running via Ollama
4. Streams the model's **live reasoning chain** and final recommendation back to the UI
5. Presents product cards with **Add to Cart** functionality

**Zero data leaves the device. No API costs. Full explainability.**

---

## Architecture

```
Customer Query
      │
      ▼
┌─────────────────────┐
│  React Frontend     │  ← Shopping cart UI + AI assistant panel
│  (ActiveEdge UI)    │
└────────┬────────────┘
         │ HTTP / SSE streaming
         ▼
┌─────────────────────┐
│  FastAPI Backend    │  ← RAG orchestration layer
└────────┬────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌──────────────────┐
│Ollama │  │   pgvector DB    │
│Deep   │  │                  │
│Seek   │  │ Product embeddings│
│R1 7B  │  │ (all-MiniLM-L6)  │
└───────┘  └──────────────────┘
                   │
                   ▼
         ┌──────────────────┐
         │   Medusa v2      │  ← Product catalogue (standalone)
         │   (separate repo)│
         └──────────────────┘
```

### Why RAG?

Instead of sending all products to the model (which breaks at scale), we:
- Embed every product description as a **384-dimensional vector**
- At query time, embed the user's query and find the **top 5 most semantically similar products**
- Only those products are sent to DeepSeek — scales to millions of products

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | DeepSeek-R1 7B via Ollama |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Search | pgvector (PostgreSQL extension) |
| Backend | Python FastAPI |
| Frontend | React + TypeScript |
| Ecommerce | Medusa v2 (separate service) |
| Database | PostgreSQL + pgvector (Docker) |

---

## Prerequisites

- macOS with Apple Silicon (M1/M2/M3) or Windows with 16GB+ RAM
- [Ollama](https://ollama.com) installed
- Docker Desktop
- Node.js 18+
- Python 3.10+
- Medusa v2 store running separately

---

## Getting Started

### 1. Pull the reasoning model

```bash
ollama pull deepseek-r1:7b
```

### 2. Start the database

```bash
docker run --name edge-commerce-db \
  -e POSTGRES_USER=medusa-store \
  -e POSTGRES_PASSWORD=medusa-store \
  -e POSTGRES_DB=medusa-store \
  -p 5434:5432 \
  -d pgvector/pgvector:pg16
```

### 3. Set up the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install fastapi uvicorn httpx python-dotenv pgvector psycopg2-binary sentence-transformers
```

Create `backend/.env`:
```
MEDUSA_URL=http://127.0.0.1:9000
OLLAMA_URL=http://127.0.0.1:11434
DEFAULT_MODEL=deepseek-r1:7b
MEDUSA_PUBLISHABLE_KEY=your_key_here
DB_URL=postgresql://medusa-store:medusa-store@127.0.0.1:5434/medusa-store
```

### 4. Embed your products

```bash
cd backend
python3 embed_products.py
```

### 5. Start the backend

```bash
uvicorn main:app --reload --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm start
```

Visit **http://localhost:3000** 🚀

---

## Key Concepts

### Reasoning at the Edge
DeepSeek-R1 is a **reasoning model** — before answering, it thinks through the problem step by step. This thinking chain is streamed live to the UI, giving full transparency into why products are recommended.

### Vector Embeddings
Each product description is converted to a list of 384 numbers that captures its semantic meaning. Similar products have similar vectors — enabling search by *meaning* rather than keywords.

### Cosine Similarity
pgvector finds relevant products by calculating the angle between the query vector and every product vector. A score of `1.0` = identical meaning, `0.0` = completely unrelated (orthogonal).

---

## Project Structure

```
edge-commerce-ai/
├── backend/
│   ├── main.py              # FastAPI app + RAG endpoints
│   ├── embed_products.py    # Product ingestion + embedding script
│   ├── add_products.py      # Seed products via Medusa Admin API
│   └── .env                 # Environment variables (not committed)
└── frontend/
    ├── src/
    │   ├── App.tsx           # Main React component
    │   └── App.css           # Styling
    └── public/
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check + model info |
| GET | `/products` | Fetch all products from Medusa |
| POST | `/recommend` | RAG recommendation (streaming SSE) |
| POST | `/search` | Debug: show pgvector similarity results |

---

## Roadmap

- [ ] Azure deployment (Azure Container Apps + Azure AI Foundry)
- [ ] Redis caching layer for frequent queries
- [ ] Customer order history context
- [ ] Multi-agent architecture (planner + critic agents)
- [ ] Voice interface

---

## Built With

This project was built as a demonstration of **Reasoning at the Edge** — one of the key AI trends of 2026. It shows how small, capable reasoning models can deliver production-grade AI features without sending sensitive data to the cloud.

---

*Built by Steve Brockie — AI Consultant*
