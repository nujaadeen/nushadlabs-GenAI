"""
Central configuration for the local RAG prototype.
Change values here; ingest.py and query.py pick them up automatically.
"""

# --- Embedding model (sentence-transformers) ---
# BAAI/bge-small-en-v1.5  → 384-dim, fast, good quality
# BAAI/bge-base-en-v1.5   → 768-dim, better quality, slower
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# BGE query instruction — prepended to the QUERY embedding only (not documents).
# bge-small-en-v1.5 retrieves significantly better with this prefix at query time.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# --- Chat LLM (served by Ollama locally) ---
# Default: llama3.2:3b  → fast, GPU-resident on 4 GB VRAM
# To use the larger model: ollama pull llama3.1:8b, then set LLM_MODEL = "llama3.1:8b"
LLM_MODEL = "llama3.2:3b"

# Ollama's local API base URL
OLLAMA_BASE_URL = "http://localhost:11434"

# Max tokens the LLM should generate per answer — caps latency on long responses.
LLM_NUM_PREDICT = 250

# Keep the model loaded between queries. "30m" = 30 minutes; -1 = keep forever.
LLM_KEEP_ALIVE = "30m"

# --- Chunking ---
# CHUNK_SIZE: max tokens per chunk.
#   Smaller → more chunks, finer-grained retrieval, less context per chunk.
#   Larger  → fewer chunks, more context per chunk, may dilute relevance scores.
CHUNK_SIZE = 350

# CHUNK_OVERLAP: tokens shared between consecutive chunks.
#   Higher → smoother context across chunk boundaries, more storage cost.
#   Zero   → hard cuts; a sentence split across a boundary is lost.
CHUNK_OVERLAP = 60

# --- Retrieval ---
# TOP_K: how many chunks to retrieve per question.
#   Higher → more context for the LLM but also more noise.
#   Lower  → tighter retrieval, may miss relevant material.
TOP_K = 8

# COMPOUND_K: how many chunks to retrieve for the "compound question" step.
#   This is a second retrieval pass after reformulating the question to be more specific.
#   Higher → more chances to find the right info after reformulation, but more latency
COMPOUND_K = 3

# MAX_CONTEXT_CHUNKS: hard cap on chunks actually sent to the LLM.
#   Retrieving more than this (TOP_K >= MAX_CONTEXT_CHUNKS) lets the vector
#   search cast a wider net while keeping the prompt tight.
MAX_CONTEXT_CHUNKS = 5

# --- Paths ---
# ChromaDB will persist its data here (relative to project root).
CHROMA_DIR = "./chroma_store"

# Folder scanned for PDFs by ingest.py (all *.pdf files inside are ingested).
DATA_DIR = "./data"

# ChromaDB collection name for documents.
COLLECTION_DOCS = "rag_docs"

# ChromaDB collection name for products.
COLLECTION_PRODUCTS = "products"

# --- Routing mode ---
# "hybrid" (default) — deterministic router is the front door; escalates to the
#                      tool-using agent only when intent == "agent".
# "router"           — never escalate; "agent" intent falls back to product_rag.
# "agent"            — bypass the router entirely; every query goes to agent_stream.
ROUTER_MODE = "hybrid"

# --- Analytics formatting ---
# When True, ask the LLM for a one-line intro before the Python-formatted list.
# When False (default), skip the LLM entirely — SQL + Python format only (<1 s).
ANALYTICS_LLM_INTRO = False

# --- Tenant registry ---
# Maps integer tenant IDs to display metadata used in system prompts.
# Add a new entry here whenever you onboard a new business.
TENANT_REGISTRY: dict[int, dict] = {
    1: {
        "name": "NovaSpark Technologies",
        "description": "a B2B data infrastructure and AI software company",
    },
    2: {
        "name": "FreshMart Grocery Co.",
        "description": "a regional grocery chain offering fresh produce, home delivery, and loyalty rewards",
    },
    3: {
        "name": "Grain & Glory Artisan Bakery",
        "description": "an artisan bakery and patisserie specialising in sourdough, viennoiserie, and custom cakes",
    },
}
