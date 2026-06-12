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
LLM_NUM_PREDICT = 400

# Keep the model loaded between queries (seconds). -1 = keep forever.
LLM_KEEP_ALIVE = -1

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

# --- Paths ---
# ChromaDB will persist its data here (relative to project root).
CHROMA_DIR = "./chroma_store"

# Folder scanned for PDFs by ingest.py (all *.pdf files inside are ingested).
DATA_DIR = "./data"

# ChromaDB collection name – change if you want separate collections per doc.
COLLECTION_NAME = "rag_docs"
