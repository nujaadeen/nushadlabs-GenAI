# Local RAG Prototype

A minimal, fully local Retrieval-Augmented Generation system built from raw components — no LangChain, no LlamaIndex.

```
PDF  →  PyMuPDF  →  cleanup  →  token-chunks  →  sentence-transformers  →  ChromaDB
                                                                                ↓
Question  →  BGE-prefixed embed  →  top-k retrieve  →  prompt  →  Ollama  →  Answer
```

---

## Prerequisites

| Tool | Install |
|------|---------|
| Python 3.10+ | [python.org](https://python.org) |
| Ollama | [ollama.com](https://ollama.com) |
| llama3.2:3b | `ollama pull llama3.2:3b` |

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

### 2. Start Ollama

```bash
ollama serve          # keep this running in a separate terminal
```

### 3. Ingest

```bash
python ingest.py
# or specify a path:
python ingest.py --pdf data/my_company_brochure.pdf

# Override chunking / model without editing config.py:
python ingest.py --chunk-size 512 --chunk-overlap 50 --embed-model BAAI/bge-small-en-v1.5
```

This will:
- Extract text from each PDF via PyMuPDF (better than pypdf for complex layouts)
- Apply a cleanup pass that fixes common extraction artefacts (e.g. `"99. 9 %"` → `"99.9%"`)
- Split into overlapping token-windows (see `CHUNK_SIZE` / `CHUNK_OVERLAP` in `config.py`)
- Embed every chunk with `sentence-transformers` (document embeddings, no prefix)
- Persist everything in ChromaDB under `./chroma_store/`

### 4. Query

```bash
# Single question
python query.py "What products does the company offer?"

# Interactive REPL (Ctrl-C to quit)
python query.py

# Override retrieval settings at runtime:
python query.py --top-k 5 --max-context-chunks 3 "What products does the company offer?"
```

> **Note:** `--embed-model` in `query.py` must match the model used during ingest — mismatched models produce wrong results.

For every question you will see:
- Whether the question was split into sub-queries (compound question handling)
- **Retrieved chunks** with their cosine distance scores
- **The full prompt** sent to the LLM
- **The LLM's answer**
- **Timing breakdown**: query embedding / vector search / LLM generation (separately)

---

## Configuration knobs (`config.py`)

| Variable | Default | What changing it does |
|---|---|---|
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Swapping to `bge-base-en-v1.5` gives 768-dim vectors and better retrieval quality at the cost of speed and memory. |
| `BGE_QUERY_INSTRUCTION` | `"Represent this sentence for searching relevant passages: "` | Prepended to the query embedding only. bge-small uses this instruction at retrieval time for better accuracy. |
| `LLM_MODEL` | `llama3.2:3b` | Any model pulled with Ollama. **To use the larger model:** `ollama pull llama3.1:8b` then set `LLM_MODEL = "llama3.1:8b"` in `config.py`. |
| `LLM_NUM_PREDICT` | `400` | Max tokens generated per answer. Caps latency on verbose responses. |
| `LLM_KEEP_ALIVE` | `-1` | Seconds to keep the model loaded between queries. `-1` = keep forever (fastest interactive use). |
| `CHUNK_SIZE` | `350` | Tokens per chunk. Smaller = finer retrieval granularity; larger = more context per chunk. |
| `CHUNK_OVERLAP` | `60` | Tokens shared between adjacent chunks. Prevents facts from being split across a hard boundary. |
| `TOP_K` | `8` | Chunks retrieved per question (or per sub-question for compound queries). |
| `CHROMA_DIR` | `./chroma_store` | Where ChromaDB persists data. |
| `COLLECTION_NAME` | `rag_docs` | ChromaDB collection name. |

> **After changing `CHUNK_SIZE`, `CHUNK_OVERLAP`, or `EMBED_MODEL`, re-run `python ingest.py`** — the existing chunks and embeddings are incompatible with the new settings.

---

## Experimentation

### Run the grid-search experiment

Sweeps chunk sizes `[256, 512, 1024]`, overlaps `[0, 50, 100]`, k values `[3, 5, 8]`, and two embedding models — all against the eval questions in `eval/questions.yaml`.

```bash
pip install pyyaml       # one-time
python experiment.py
```

Sample output:

```
[1/2] Loading model: BAAI/bge-small-en-v1.5 …
   chunk_size= 256, overlap=  0 → 15 chunks  hit@3=62%  hit@5=75%  hit@8=87%
   chunk_size= 512, overlap= 50 → 13 chunks  hit@3=87%  hit@5=100% hit@8=100%
   ...

═══════════════════════════════════════════════════════════════
 RESULTS TABLE  (8 eval questions — sorted by Hit Rate ↓)
═══════════════════════════════════════════════════════════════
   # │ Model                  │ ChkSz │ Ovlp │  K │ Chunks │  Top-1 Sim │   Hit Rate
 ───┼────────────────────────┼───────┼──────┼────┼────────┼────────────┼───────────
   1 │ bge-small-en-v1.5      │   512 │   50 │  3 │     13 │     0.7432 │   100.0%  ★
 ...
```

Narrow the sweep:

```bash
python experiment.py --models BAAI/bge-small-en-v1.5  --chunk-sizes 256 512
python experiment.py --questions eval/questions.yaml   # custom eval file
```

### Edit the eval set

`eval/questions.yaml` contains 8 factual questions about the NovaSpark PDFs. Each entry pairs a question with a keyword that must appear (case-insensitive) in at least one of the top-k chunks for a "hit":

```yaml
questions:
  - question: "How many employees does NovaSpark have?"
    keyword: "280"
```

Add your own questions to measure coverage on facts that matter to you.

---

## Streamlit app (optional)

Install Streamlit and launch the live UI:

```bash
pip install streamlit
streamlit run app.py
```

The app lets you drag sliders for chunk size, overlap, and k and immediately see the re-indexed results and a fresh LLM answer — no command line needed.

The CLI (`ingest.py`, `query.py`) works without Streamlit installed.

---

## GPU acceleration

If an NVIDIA GPU is present, Ollama detects it automatically via CUDA and loads the model onto the GPU. No extra configuration is needed.

- **GPU**: model weights stay in VRAM; typical generation speed 30–60 tok/s on a 3050.
- **CPU-only**: Ollama falls back to CPU automatically; generation is 3–10× slower.

To verify which device Ollama is using, check the log output of `ollama serve` — it prints the detected backend at startup.

To switch between models:

```bash
# Fast default (fits in 4 GB VRAM)
# LLM_MODEL = "llama3.2:3b"   ← already set in config.py

# Higher quality, needs ~6 GB VRAM (or more RAM for CPU)
ollama pull llama3.1:8b
# then edit config.py: LLM_MODEL = "llama3.1:8b"
```

---

## Understanding the scores

ChromaDB stores **cosine distance** (0 = identical, 2 = opposite).  
`query.py` also prints the equivalent **similarity = 1 − distance** for intuition.

- Distance < 0.2 → strong match
- Distance 0.2–0.5 → moderate match
- Distance > 0.5 → weak match; the chunk may not be relevant

---

## Timing breakdown

Every answer prints three timings so you can see where the time goes:

```
TIMING BREAKDOWN
  Query embedding :     8.3 ms
  Vector search   :     2.1 ms
  LLM generation  :  4832.7 ms  ← bottleneck
  Total (wall)    :  4843.1 ms  (4.84s)
```

Retrieval (embed + search) is typically under 50 ms. The LLM is the bottleneck.
Use `llama3.2:3b` for interactive use; switch to `llama3.1:8b` when answer quality matters more than speed.

---

## Project layout

```
rag_prototype/
├── config.py               # all tunables
├── ingest.py               # PDF → PyMuPDF → cleanup → chunks → embeddings → ChromaDB
│                           #   CLI: --chunk-size  --chunk-overlap  --embed-model
├── query.py                # question → embed → retrieve → prompt → Ollama → answer
│                           #   CLI: --top-k  --max-context-chunks  --embed-model
├── experiment.py           # grid search: chunk sizes × overlaps × k × models → hit-rate table
├── app.py                  # Streamlit UI (optional; pip install streamlit)
├── eval/
│   └── questions.yaml      # 8 eval questions with expected keywords
├── inspect_embeddings.py   # tokenizer + embedding teaching tool
├── requirements.txt
├── README.md
├── data/                   # drop your PDFs here
└── chroma_store/           # auto-created by ingest.py
```

---

## Troubleshooting

**`Collection not found`** — run `python ingest.py` first.

**`Could not reach Ollama`** — make sure `ollama serve` is running and the model is pulled (`ollama pull llama3.2:3b`).

**No text extracted from PDF** — the PDF is likely scanned/image-only. You need OCR (e.g. `pytesseract`) before ingesting.

**Answer ignores the context** — try lowering `CHUNK_SIZE` for finer retrieval, or raising `TOP_K` to give the LLM more material.
