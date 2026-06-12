# Local RAG Prototype

A minimal, fully local Retrieval-Augmented Generation system built from raw components — no LangChain, no LlamaIndex.

```
PDF  →  pypdf  →  token-chunks  →  sentence-transformers  →  ChromaDB
                                                                  ↓
Question  →  embed  →  top-k retrieve  →  prompt  →  Ollama  →  Answer
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | [python.org](https://python.org) |
| Ollama | [ollama.com](https://ollama.com) |
| llama3.1:8b | `ollama pull llama3.1:8b` |

---

## Setup

```bash
cd rag_prototype
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Workflow

### 1. Drop your PDF

```
rag_prototype/data/document.pdf
```

If your file has a different name, update `PDF_PATH` in `config.py`.

### 2. Start Ollama

```bash
ollama serve          # keep this running in a separate terminal
```

### 3. Ingest

```bash
python ingest.py
# or specify a path:
python ingest.py --pdf data/my_company_brochure.pdf
```

This will:
- Extract all text from the PDF
- Split it into overlapping token-windows (see `CHUNK_SIZE` / `CHUNK_OVERLAP`)
- Embed every chunk with `sentence-transformers`
- Persist everything in ChromaDB under `./chroma_store/`

### 4. Query

```bash
# Single question
python query.py "What products does the company offer?"

# Interactive REPL (Ctrl-C to quit)
python query.py
```

For every question you will see:
- **Retrieved chunks** with their cosine distance scores
- **The full prompt** sent to the LLM
- **The LLM's answer**

### 5. Inspect embeddings (optional learning tool)

```bash
python inspect_embeddings.py
```

Prints the tokenizer output, the embedding vector dimensions, and cosine similarity between example sentences so you can develop intuition for the space.

---

## Configuration knobs (`config.py`)

| Variable | Default | What changing it does |
|---|---|---|
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Swapping to `bge-base-en-v1.5` gives 768-dim vectors and better retrieval quality at the cost of speed and memory. |
| `LLM_MODEL` | `llama3.1:8b` | Any model you have pulled with Ollama (e.g. `mistral:7b`, `phi3:mini`). Bigger = slower but smarter answers. |
| `CHUNK_SIZE` | `256` | Tokens per chunk. Smaller chunks = finer retrieval granularity but less surrounding context. Larger chunks = more context per retrieved piece but scores become noisier. |
| `CHUNK_OVERLAP` | `32` | Tokens shared between adjacent chunks. Increase if answers feel truncated at chunk boundaries. Set to 0 for hard cuts. |
| `TOP_K` | `4` | Chunks retrieved per question. Increase for broad questions, decrease to force the LLM to use only the best match. |
| `CHROMA_DIR` | `./chroma_store` | Where ChromaDB persists data. Change to use a different or shared store. |
| `PDF_PATH` | `./data/document.pdf` | Default PDF if you don't pass `--pdf` to `ingest.py`. |
| `COLLECTION_NAME` | `rag_docs` | ChromaDB collection name. Change to maintain separate collections for different documents. |

> **After changing `CHUNK_SIZE`, `CHUNK_OVERLAP`, or `EMBED_MODEL`, re-run `ingest.py`** — the existing chunks and embeddings are incompatible with the new settings.

---

## Understanding the scores

ChromaDB stores **cosine distance** (0 = identical, 2 = opposite).  
`query.py` also prints the equivalent **similarity = 1 − distance** for intuition.

- Distance < 0.2 → strong match
- Distance 0.2–0.5 → moderate match
- Distance > 0.5 → weak match; the chunk may not be relevant

---

## Project layout

```
rag_prototype/
├── config.py               # all tunables
├── ingest.py               # PDF → chunks → embeddings → ChromaDB
├── query.py                # question → retrieve → prompt → Ollama → answer
├── inspect_embeddings.py   # tokenizer + embedding teaching tool
├── requirements.txt
├── README.md
├── data/                   # drop your PDF here
└── chroma_store/           # auto-created by ingest.py
```

---

## Troubleshooting

**`Collection not found`** — run `python ingest.py` first.

**`Could not reach Ollama`** — make sure `ollama serve` is running and the model is pulled (`ollama pull llama3.1:8b`).

**No text extracted from PDF** — the PDF is likely scanned/image-only. You need OCR (e.g. `pytesseract`) before ingesting.

**Answer ignores the context** — try lowering `CHUNK_SIZE` for finer retrieval, or raising `TOP_K` to give the LLM more material.
