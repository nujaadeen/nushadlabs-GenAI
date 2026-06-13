# rag_agent_backend

A fully-local, multi-tenant Retrieval-Augmented Generation backend — no LangChain, no LlamaIndex.

```
PDF → PyMuPDF → cleanup → token-chunks → sentence-transformers → ChromaDB
                                                                       ↓
Question → intent router → (SQL | RAG | tool-using agent) → Ollama → SSE stream
```

---

## Project structure

```
rag_agent_backend/
├── src/
│   └── rag_agent/              # importable Python package
│       ├── __init__.py
│       ├── config.py           # all tuneable knobs in one place
│       ├── api.py              # FastAPI app — SSE /chat, /health, admin /ingest
│       ├── ingestion/
│       │   ├── ingest.py       # PDF → chunk → embed → ChromaDB pipeline
│       │   └── sync_products.py# ERP product rows → ChromaDB (incremental)
│       ├── retrieval/
│       │   ├── query.py        # embed, retrieve(), ask_ollama*()
│       │   ├── router.py       # intent classifier + hybrid front door
│       │   └── agent.py        # tool-using agent loop (Ollama function-calling)
│       ├── tools/
│       │   └── analytics.py    # tenant-scoped SQL analytics helpers
│       └── db/
│           ├── connection.py   # SQLAlchemy engine + Product ORM model
│           ├── seed.sql        # seed data for the ERP database
│           └── docker-compose.yml  # Postgres container
├── tests/
│   ├── test_isolation.py       # tenant isolation security tests
│   └── test_routing.py         # router regex / heuristic unit tests
├── experiments/
│   ├── experiment.py           # chunk-size / k / model grid-search harness
│   ├── inspect_embeddings.py   # teaching tool — tokenizer + embedding output
│   └── eval/
│       └── questions.yaml      # evaluation question set for experiment.py
├── data/                       # PDFs per tenant (tenant_N/resources/*.pdf)
├── chroma_store/               # ChromaDB persistent store (auto-created)
├── web/                        # standalone HTML UIs
├── pyproject.toml              # src-layout editable install config
└── requirements.txt            # runtime dependencies
```

**Top-level siblings (not inside this folder):**
- `agent_ui/` — Vite + vanilla JS frontend (separate npm project)
- `docs/ARCHITECTURE.md` — system design overview

---

## Dev setup

```bash
cd rag_agent_backend

# 1. Activate the shared venv (or create one)
source ../.venv/bin/activate   # adjust path if needed

# 2. Install the package in editable mode (imports resolve via src layout)
pip install -e .

# 3. Install runtime dependencies
pip install -r requirements.txt
```

---

## Start the database

```bash
docker compose -f src/rag_agent/db/docker-compose.yml up -d
# Seed it once:
psql -h localhost -p 5433 -U erp_user -d erp_db -f src/rag_agent/db/seed.sql
```

---

## Ingest documents

```bash
# Ingest all PDFs for a tenant (run from rag_agent_backend/)
python -m rag_agent.ingestion.ingest --tenant-id 1

# Ingest a single PDF
python -m rag_agent.ingestion.ingest --tenant-id 2 --pdf data/tenant_2/resources/freshmart_overview.pdf

# Sync ERP products into ChromaDB
python -m rag_agent.ingestion.sync_products
python -m rag_agent.ingestion.sync_products --full   # rebuild from scratch
```

---

## Run the API

```bash
uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

---

## Run tests

```bash
pytest -q
```

---

## Run the web UIs

**Agent UI (Vite — recommended)**

```bash
cd ../agent_ui
cp .env.example .env     # edit VITE_PROXY_TARGET if backend isn't on :8000
npm install
npm run dev              # → http://localhost:5173
```

**Standalone HTML console** (no build step)

```bash
# Serve the file however you like, e.g.:
python -m http.server 8080 --directory web/
# Then open http://localhost:8080/agent_console.html
```

---

## Routing modes (`config.ROUTER_MODE`)

| Mode | Behaviour |
|------|-----------|
| `"hybrid"` (default) | Fast deterministic router as front door; escalates to the tool-using agent only for multi-step questions |
| `"router"` | Never escalates; agent intent falls back to `product_rag` |
| `"agent"` | Bypasses classification entirely; every query goes to the agent loop |

---

## Key config knobs (`src/rag_agent/config.py`)

| Variable | Default | Description |
|---|---|---|
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Sentence-transformer model used for both ingest and query |
| `LLM_MODEL` | `llama3.2:3b` | Ollama model for generation and classification |
| `CHUNK_SIZE` | `350` | Tokens per chunk during ingest |
| `TOP_K` | `8` | Chunks retrieved per query |
| `ANALYTICS_LLM_INTRO` | `False` | Add an LLM one-liner intro to analytics answers (adds ~3 s) |
| `ROUTER_MODE` | `"hybrid"` | See routing modes above |
