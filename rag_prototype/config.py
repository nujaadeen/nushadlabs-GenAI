"""
Central configuration for the local RAG prototype.
Change values here; ingest.py and query.py pick them up automatically.
"""

# --- Embedding model (sentence-transformers) ---
# BAAI/bge-small-en-v1.5  → 384-dim, fast, good quality
# BAAI/bge-base-en-v1.5   → 768-dim, better quality, slower
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# --- Chat LLM (served by Ollama locally) ---
# Make sure you've run: ollama pull llama3.1:8b
LLM_MODEL = "llama3.1:8b"

# Ollama's local API base URL
OLLAMA_BASE_URL = "http://localhost:11434"

# --- Chunking ---
# CHUNK_SIZE: max tokens per chunk.
#   Smaller → more chunks, finer-grained retrieval, less context per chunk.
#   Larger  → fewer chunks, more context per chunk, may dilute relevance scores.
CHUNK_SIZE = 256

# CHUNK_OVERLAP: tokens shared between consecutive chunks.
#   Higher → smoother context across chunk boundaries, more storage cost.
#   Zero   → hard cuts; a sentence split across a boundary is lost.
CHUNK_OVERLAP = 32

# --- Retrieval ---
# TOP_K: how many chunks to retrieve per question.
#   Higher → more context for the LLM but also more noise.
#   Lower  → tighter retrieval, may miss relevant material.
TOP_K = 4

# --- Paths ---
# ChromaDB will persist its data here (relative to project root).
CHROMA_DIR = "./chroma_store"

# Folder scanned for PDFs by ingest.py (all *.pdf files inside are ingested).
DATA_DIR = "./data"

# ChromaDB collection name – change if you want separate collections per doc.
COLLECTION_NAME = "rag_docs"
