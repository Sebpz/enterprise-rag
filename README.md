# 🔬 Enterprise RAG Platform

A production-quality AI research assistant built on the ArXiv corpus. Ask natural language questions about ML papers, get cited answers, or trigger a multi-agent system for complex research queries.

Built as a portfolio project demonstrating senior AI engineer skills across 9 modules.

---

## 🗺️ Architecture

```
User → Next.js Frontend
     → FastAPI Gateway (auth, rate limiting, versioning)
     → RAG Core  OR  LangGraph Multi-Agent
     → Guardrails Layer (input + output)
     → Qdrant Vector Store + PostgreSQL + Redis
     → Langfuse Traces + Grafana Dashboards
```

---

## 📦 Modules

| # | Module | Key Skills |
|---|--------|------------|
| 1 | [Ingestion Pipeline](./ingestion/README.md) | Chunking · Embedding · Qdrant · Metadata |
| 2 | [RAG Core](./rag/README.md) | Hybrid search · RRF · Reranking · Streaming |
| 3 | [API & Serving](./api/README.md) | FastAPI · Docker · Rate limiting · Auth |
| 4 | [Guardrails & Safety](./guardrails/README.md) | Presidio · Topic filter · Faithfulness judge |
| 5 | [Evaluation Framework](./evals/README.md) | RAGAs · Golden dataset · CI gate |
| 6 | [Monitoring Dashboard](./monitoring/README.md) | Langfuse · Prometheus · Grafana |
| 7 | [LangGraph Multi-Agent](./agents/README.md) | Orchestrator · Tool agents · Agentic guardrails |
| 8 | [Next.js Frontend](./frontend/README.md) | Chat UI · Streaming · Eval dashboard |
| 9 | [Fine-Tuning Experiment](./fine_tuning/README.md) | LoRA · QLoRA · Citation formatting · W&B |

---

## 🚀 Quickstart

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- OpenAI API key (or run fully local with Ollama)

### 1. Clone and configure
```bash
git clone https://github.com/YOUR_USERNAME/enterprise-rag.git
cd enterprise-rag
cp .env.example .env
# Edit .env and add your API keys
```

### 2. Spin up all services
```bash
docker compose up -d
```

This starts:
| Service | URL |
|---------|-----|
| FastAPI | http://localhost:8000/docs |
| Next.js | http://localhost:3000 |
| Qdrant | http://localhost:6333/dashboard |
| Langfuse | http://localhost:3001 |
| Grafana | http://localhost:3002 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Ingest ArXiv data
```bash
# Ingest 10k papers from cs.AI category (good starting point)
docker compose exec api python -m ingestion.pipeline --limit 10000 --category cs.AI
```

### 4. Run your first query
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "X-API-Key: dev-key-local" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the attention mechanism?", "mode": "rag"}'
```

---

## 🛠️ Development

### Run API locally (without Docker)
```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Run frontend locally
```bash
cd frontend
npm install
npm run dev
```

### Run evals
```bash
python -m evals.run_evals --config v1
```

---

## 📁 Project Structure

```
enterprise-rag/
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # All environment variables
├── ingestion/                  # Module 1 — data pipeline
├── rag/                        # Module 2 — retrieval + generation
├── api/                        # Module 3 — FastAPI serving layer
├── guardrails/                 # Module 4 — safety layer
├── evals/                      # Module 5 — evaluation framework
├── monitoring/                 # Module 6 — observability
├── agents/                     # Module 7 — LangGraph multi-agent
├── frontend/                   # Module 8 — Next.js UI
├── fine_tuning/                # Module 9 — LoRA fine-tuning
└── scripts/                    # Utility scripts
```

---

## 🔑 Environment Variables

See [.env.example](./.env.example) for all required variables. Key ones:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (or leave blank for Ollama) |
| `COHERE_API_KEY` | Cohere Rerank API key |
| `QDRANT_URL` | Vector store URL (default: http://localhost:6333) |
| `DATABASE_URL` | PostgreSQL connection string |
| `LLM_PROVIDER` | `openai` or `ollama` |

---

## 🧪 Running Tests

```bash
# Unit tests
pytest tests/ -v

# Eval suite (requires data to be ingested)
python -m evals.run_evals

# Guardrail tests
pytest guardrails/tests/ -v
```

---

## 📊 Key Interview Talking Points

1. **Hybrid search** — dense (Qdrant ANN) + sparse (BM25) fused with RRF
2. **Agentic guardrails** — per-node validation + budget tracking in LangGraph state
3. **Eval-driven development** — RAGAs CI gate blocks prompt regressions
4. **Fine-tuning experiment** — QLoRA on Mistral-7B, schema compliance 71% → 94%
5. **Full observability** — every token, tool call, and cost tracked in Langfuse

---

## 🗓️ Build Order

Build modules in order — each one depends on the previous:

```
Week 1 → Module 1 (Ingestion)
Week 2 → Module 2 (RAG Core)
Week 3 → Module 3 (API + Docker)
Week 4 → Module 4 (Guardrails)
Week 5 → Module 5 (Evaluation)
Week 6 → Module 6 (Monitoring)
Week 7 → Module 7 (LangGraph Agents)
Week 8 → Module 8 (Next.js Frontend)
Week 9 → Module 9 (Fine-Tuning)
```
