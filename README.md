# nushadlabs-GenAI

A hands-on repository for building and exploring **Generative AI** systems — from tokenization fundamentals to a production-shaped, fully-local RAG agent backend.

---

## Repository layout

```
nushadlabs-GenAI/
├── rag_agent_backend/   # Multi-tenant RAG agent backend (Python package)
├── agent_ui/            # Vite + vanilla JS frontend for the backend
├── docs/
│   └── ARCHITECTURE.md  # System design overview
└── README.md            # This file
```

---

## Projects

### `rag_agent_backend/` — Local RAG Agent Backend

A fully-local, multi-tenant Retrieval-Augmented Generation backend with intent routing and tool-calling. No LangChain, no LlamaIndex.

```
PDF → PyMuPDF → token-chunks → sentence-transformers → ChromaDB
                                                             ↓
Question → intent router → (SQL | RAG | tool-using agent) → Ollama → SSE stream
```

**Key capabilities:**
- **Hybrid intent router** — classifies questions deterministically (regex → keyword → LLM); escalates to a tool-using agent only for multi-step questions
- **Tool-using agent loop** — Ollama function-calling with 6 tools (doc search, product search, SQL analytics, product lookup by ID)
- **Multi-tenant isolation** — every ChromaDB query and SQL call is hard-filtered by `tenant_id`; the model never sees or controls it
- **Streaming API** — FastAPI + Server-Sent Events; token-by-token output, tool-call events, and cited sources

**Quick start:**
```bash
cd rag_agent_backend
source ../.venv/bin/activate
pip install -e .
pip install -r requirements.txt

# Start Postgres
docker compose -f src/rag_agent/db/docker-compose.yml up -d

# Ingest documents and sync products
python -m rag_agent.ingestion.ingest --tenant-id 1
python -m rag_agent.ingestion.sync_products --full

# Start the API
uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

See [`rag_agent_backend/README.md`](rag_agent_backend/README.md) for the full guide (structure, all CLI commands, config knobs, routing modes).

---

### `agent_ui/` — Web Frontend

A Vite + vanilla JS single-page app that connects to the backend via SSE and shows three live panes: streaming answer, tool calls, and a raw event log.

```bash
cd agent_ui
cp .env.example .env   # set VITE_PROXY_TARGET=http://localhost:8000
npm install
npm run dev            # → http://localhost:5173
```

---

## Stack

| Layer | Technology |
|---|---|
| Embeddings | `sentence-transformers` (BAAI/bge-small-en-v1.5) |
| Vector store | ChromaDB (persistent, local) |
| LLM + function-calling | Ollama (`llama3.2:3b`) |
| API | FastAPI + SSE streaming |
| Database | PostgreSQL via SQLAlchemy |
| Frontend | Vite + vanilla JS (no framework) |
| Tests | pytest |
