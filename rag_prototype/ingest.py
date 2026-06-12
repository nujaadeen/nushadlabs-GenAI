"""
ingest.py — Load all PDFs in the data folder, chunk by tokens, embed, and store in ChromaDB.

Usage:
    python ingest.py               (ingests every *.pdf in config.DATA_DIR)
    python ingest.py --pdf PATH    (ingests a single specific PDF)
"""

import argparse
import sys
from pathlib import Path

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

import config


# ---------------------------------------------------------------------------
# PDF loading
# ---------------------------------------------------------------------------

def load_pdf(path: str) -> str:
    """Extract all text from a PDF, joining pages with a newline."""
    reader = PdfReader(path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text.strip())
    full_text = "\n".join(pages)
    print(f"[ingest] Loaded {len(reader.pages)} pages, {len(full_text):,} characters from '{path}'")
    return full_text


# ---------------------------------------------------------------------------
# Token-based chunking
# ---------------------------------------------------------------------------

def chunk_by_tokens(text: str, tokenizer, chunk_size: int, overlap: int) -> list[str]:
    """
    Split `text` into chunks of at most `chunk_size` tokens, with `overlap`
    tokens of shared context between consecutive chunks.

    Strategy:
      1. Tokenize the entire text once.
      2. Slide a window of `chunk_size` tokens, stepping by (chunk_size - overlap).
      3. Decode each window back to a string.
    """
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    total_tokens = len(token_ids)
    step = max(1, chunk_size - overlap)

    chunks = []
    start = 0
    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        window = token_ids[start:end]
        chunk_text = tokenizer.decode(window, skip_special_tokens=True)
        chunks.append(chunk_text.strip())
        if end == total_tokens:
            break
        start += step

    return chunks


# ---------------------------------------------------------------------------
# Stable chunk ID
# ---------------------------------------------------------------------------

def make_chunk_id(pdf_path: str, chunk_index: int) -> str:
    """Deterministic ID so re-ingesting the same PDF is idempotent."""
    stem = Path(pdf_path).stem
    return f"{stem}_chunk_{chunk_index:05d}"


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest(pdf_paths: list[str]) -> None:
    # 1. Load embedding model once for all PDFs
    print(f"[ingest] Loading embedding model '{config.EMBED_MODEL}' …")
    model = SentenceTransformer(config.EMBED_MODEL)
    tokenizer = model.tokenizer

    # 2. Connect to ChromaDB and recreate the collection fresh
    print(f"[ingest] Storing in ChromaDB at '{config.CHROMA_DIR}' …")
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    try:
        client.delete_collection(config.COLLECTION_NAME)
        print(f"[ingest] Replaced existing collection '{config.COLLECTION_NAME}'")
    except Exception:
        pass
    collection = client.create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 3. Process each PDF and add its chunks to the collection
    total_chunks = 0
    for pdf_path in pdf_paths:
        print(f"\n[ingest] --- Processing: {pdf_path}")
        text = load_pdf(pdf_path)
        if not text.strip():
            print(f"[ingest] WARNING: No text extracted from '{pdf_path}' (skipping).")
            continue

        print(f"[ingest] Chunking (size={config.CHUNK_SIZE} tokens, overlap={config.CHUNK_OVERLAP}) …")
        chunks = chunk_by_tokens(text, tokenizer, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        print(f"[ingest] Created {len(chunks)} chunks")

        print(f"[ingest] Embedding {len(chunks)} chunks …")
        embeddings = model.encode(chunks, show_progress_bar=True, normalize_embeddings=True)

        ids = [make_chunk_id(pdf_path, i) for i in range(len(chunks))]
        metadatas = [{"source": Path(pdf_path).name, "chunk_index": i} for i in range(len(chunks))]

        collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)

    print(f"\n[ingest] Done. {total_chunks} total chunks from {len(pdf_paths)} PDF(s) "
          f"stored in collection '{config.COLLECTION_NAME}'.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PDFs into ChromaDB")
    parser.add_argument("--pdf", default=None, help="Ingest a single PDF instead of the whole data folder")
    args = parser.parse_args()

    if args.pdf:
        if not Path(args.pdf).exists():
            print(f"[ingest] ERROR: File not found: '{args.pdf}'")
            sys.exit(1)
        pdf_paths = [args.pdf]
    else:
        data_dir = Path(config.DATA_DIR)
        pdf_paths = sorted(data_dir.glob("*.pdf"))
        if not pdf_paths:
            print(f"[ingest] ERROR: No PDF files found in '{data_dir}'.")
            sys.exit(1)
        print(f"[ingest] Found {len(pdf_paths)} PDF(s) in '{data_dir}':")
        for p in pdf_paths:
            print(f"         - {p.name}")

    ingest([str(p) for p in pdf_paths])
