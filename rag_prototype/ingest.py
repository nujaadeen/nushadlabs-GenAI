"""
ingest.py — Load all PDFs in the data folder, chunk by tokens, embed, and store in ChromaDB.

Usage:
    python ingest.py --tenant-id TENANT_ID               (ingests every *.pdf in config.DATA_DIR)
    python ingest.py --tenant-id TENANT_ID --pdf PATH    (ingests a single specific PDF)
"""

import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

import config

# Suppress the "[transformers] Token indices sequence length > 512" warning that fires
# when chunk_by_tokens encodes the *full* PDF text before slicing.  Individual chunks
# are always ≤ _MAX_EMBED_TOKENS, so the warning is spurious for the chunking use case.
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)


# ---------------------------------------------------------------------------
# PDF loading with PyMuPDF
# ---------------------------------------------------------------------------

def load_pdf(path: str) -> str:
    """Extract text from a PDF using PyMuPDF, preserving paragraph structure."""
    doc = fitz.open(path)
    pages = []
    for page in doc:
        # get_text("text") preserves line/paragraph breaks naturally
        text = page.get_text("text") or ""
        pages.append(text.strip())
    page_count = len(doc)
    doc.close()
    full_text = "\n\n".join(pages)
    print(f"[ingest] Loaded {page_count} pages, {len(full_text):,} characters from '{path}'")
    return full_text


# ---------------------------------------------------------------------------
# Text cleanup — fix broken extraction artefacts from PDF layout engines
# ---------------------------------------------------------------------------

# Patterns that collapse spurious spaces *inside* numbers, currency, and percentages.
# Examples fixed:
#   "99. 9 %"  → "99.9%"
#   "$ 1, 999" → "$1,999"
#   "1, 400 +" → "1,400+"
#   "$ 0. 12"  → "$0.12"
#   "1 ,234"   → "1,234"
_CLEANUP_RULES: list[tuple[str, str]] = [
    # currency symbol followed by optional space then digits: "$ 1,999" → "$1,999"
    (r"(\$)\s+(\d)", r"\1\2"),
    # digit, decimal point, space(s), digit: "99. 9" → "99.9"
    (r"(\d)\.\s+(\d)", r"\1.\2"),
    # digit, space(s), percent sign: "99 %" → "99%"
    (r"(\d)\s+(%)", r"\1\2"),
    # digit, space, comma, space, digit (thousands separator): "1 , 000" → "1,000"
    (r"(\d)\s*,\s*(\d)", r"\1,\2"),
    # digit, space(s), plus sign: "1,400 +" → "1,400+"
    (r"(\d)\s+\+", r"\1+"),
]


def clean_text(text: str) -> str:
    """Apply extraction-artefact cleanup rules without destroying paragraph structure."""
    result = text
    for pattern, replacement in _CLEANUP_RULES:
        result = re.sub(pattern, replacement, result)
    return result


def _sample_before_after(raw: str, cleaned: str, n_chars: int = 600) -> None:
    """Log a before/after sample anchored on the first line that contains a number symbol."""
    print("\n[ingest] ── Text cleanup sample ──────────────────────────────────")

    # Prefer a window that actually shows number cleanup in action.
    # Search for the first line containing '%', '$', or a digit followed by '+'.
    anchor = -1
    for sym in ("%", "$"):
        pos = raw.find(sym)
        if pos != -1 and (anchor == -1 or pos < anchor):
            anchor = pos
    # also check digit+space+plus pattern
    m = re.search(r"\d\s+\+", raw)
    if m and (anchor == -1 or m.start() < anchor):
        anchor = m.start()

    if anchor != -1:
        start = max(0, raw.rfind("\n", 0, anchor) + 1)
        label = "600 chars from first line containing a number/symbol"
    else:
        start = 0
        label = "first 600 chars (no number symbols found)"

    before_sample = raw[start:start + n_chars]
    after_sample  = cleaned[start:start + n_chars]

    print(f"[ingest] BEFORE ({label}):")
    print(before_sample)
    print(f"\n[ingest] AFTER  ({label}):")
    print(after_sample)

    changed = sum(1 for a, b in zip(before_sample, after_sample) if a != b)
    if changed:
        print(f"\n[ingest] {changed} character(s) changed by cleanup in this sample.")
    else:
        print("\n[ingest] No changes in this sample (artefacts may appear elsewhere).")
    print("[ingest] ────────────────────────────────────────────────────────\n")


# ---------------------------------------------------------------------------
# Token-based chunking
# ---------------------------------------------------------------------------

# Hard limit: bge-small-en-v1.5 max_seq_length=512 (includes [CLS]+[SEP]),
# so content must fit in 510 tokens to avoid the "> 512" truncation warning.
_MAX_EMBED_TOKENS = 510


def enforce_max_tokens(chunks: list[str], tokenizer, max_tokens: int = _MAX_EMBED_TOKENS) -> list[str]:
    """Hard-split any chunk that exceeds max_tokens before embedding."""
    result: list[str] = []
    for chunk in chunks:
        ids = tokenizer.encode(chunk, add_special_tokens=False)
        if len(ids) <= max_tokens:
            result.append(chunk)
        else:
            for start in range(0, len(ids), max_tokens):
                sub = tokenizer.decode(
                    ids[start:start + max_tokens], skip_special_tokens=True
                ).strip()
                if sub:
                    result.append(sub)
    return result


def chunk_by_tokens(text: str, tokenizer, chunk_size: int, overlap: int) -> list[str]:
    """
    Split `text` into chunks of at most `chunk_size` tokens, with `overlap`
    tokens of shared context between consecutive chunks.
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

def make_chunk_id(pdf_path: str, chunk_index: int, tenant_id: int) -> str:
    """Deterministic ID so re-ingesting the same PDF+tenant is idempotent."""
    stem = Path(pdf_path).stem
    return f"{tenant_id}_{stem}_chunk_{chunk_index:05d}"


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest(pdf_paths: list[str], tenant_id: int) -> None:
    if not isinstance(tenant_id, int) or tenant_id < 1:
        raise ValueError(f"tenant_id must be a positive integer, got {tenant_id!r}")

    ingest_timestamp = datetime.now(timezone.utc).isoformat()

    # 1. Load embedding model once for all PDFs
    print(f"[ingest] Loading embedding model '{config.EMBED_MODEL}' …")
    model = SentenceTransformer(config.EMBED_MODEL)
    tokenizer = model.tokenizer

    # 2. Connect to ChromaDB — get or create the shared collection so other
    #    tenants' data is never touched.
    print(f"[ingest] Storing in ChromaDB at '{config.CHROMA_DIR}' …")
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 3. Process each PDF and upsert its chunks (idempotent per tenant+file)
    total_chunks = 0
    first_pdf = True
    for pdf_path in pdf_paths:
        print(f"\n[ingest] --- Processing: {pdf_path} (tenant: {tenant_id})")
        raw_text = load_pdf(pdf_path)
        if not raw_text.strip():
            print(f"[ingest] WARNING: No text extracted from '{pdf_path}' (skipping).")
            continue

        text = clean_text(raw_text)

        # Show before/after sample for the first PDF only (keep log readable)
        if first_pdf:
            _sample_before_after(raw_text, text)
            first_pdf = False

        print(f"[ingest] Chunking (size={config.CHUNK_SIZE} tokens, overlap={config.CHUNK_OVERLAP}) …")
        chunks = chunk_by_tokens(text, tokenizer, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
        # Cleanup must run again AFTER decode because the tokenizer re-introduces spacing
        # artefacts (e.g. "$1,999" encodes to ["$","1",",","999"] then decodes to "$ 1, 999").
        chunks = [clean_text(chunk) for chunk in chunks]
        chunks = enforce_max_tokens(chunks, tokenizer)
        token_lengths = [len(tokenizer.encode(c, add_special_tokens=False)) for c in chunks]
        print(f"[ingest] Created {len(chunks)} chunks  "
              f"(max token length: {max(token_lengths)} / {_MAX_EMBED_TOKENS} — no truncation warning)")

        print(f"[ingest] Embedding {len(chunks)} chunks …")
        # Document embeddings are stored WITHOUT the BGE query instruction prefix.
        embeddings = model.encode(chunks, show_progress_bar=True, normalize_embeddings=True)

        ids = [make_chunk_id(pdf_path, i, tenant_id) for i in range(len(chunks))]
        metadatas = [
            {
                "tenant_id": tenant_id,
                "source": Path(pdf_path).name,
                "chunk_index": i,
                "ingest_timestamp": ingest_timestamp,
            }
            for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=chunks,
            metadatas=metadatas,
        )
        total_chunks += len(chunks)

    print(f"\n[ingest] Done. {total_chunks} total chunks from {len(pdf_paths)} PDF(s) "
          f"stored in collection '{config.COLLECTION_NAME}' under tenant '{tenant_id}'.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest PDFs into ChromaDB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--tenant-id", required=True, type=int, metavar="N",
                        help="Tenant identifier (positive integer) — all ingested chunks are tagged with this ID")
    parser.add_argument("--pdf", default=None, metavar="PATH",
                        help="Ingest a single PDF instead of the tenant's resources folder")
    parser.add_argument("--chunk-size", type=int, default=None, metavar="N",
                        help=f"Tokens per chunk (config default: {config.CHUNK_SIZE})")
    parser.add_argument("--chunk-overlap", type=int, default=None, metavar="N",
                        help=f"Overlap between consecutive chunks (config default: {config.CHUNK_OVERLAP})")
    parser.add_argument("--embed-model", default=None, metavar="MODEL",
                        help=f"Sentence-transformers model ID (config default: {config.EMBED_MODEL})")
    args = parser.parse_args()

    # Apply CLI overrides in-process (does NOT edit config.py)
    if args.chunk_size is not None:
        config.CHUNK_SIZE = args.chunk_size
    if args.chunk_overlap is not None:
        config.CHUNK_OVERLAP = args.chunk_overlap
    if args.embed_model is not None:
        config.EMBED_MODEL = args.embed_model

    if args.pdf:
        if not Path(args.pdf).exists():
            print(f"[ingest] ERROR: File not found: '{args.pdf}'")
            sys.exit(1)
        pdf_paths = [args.pdf]
    else:
        data_dir = Path(config.DATA_DIR) / f"tenant_{args.tenant_id}" / "resources"
        pdf_paths = sorted(data_dir.glob("*.pdf"))
        if not pdf_paths:
            print(f"[ingest] ERROR: No PDF files found in '{data_dir}'.")
            print(f"         Expected path: {data_dir.resolve()}")
            sys.exit(1)
        print(f"[ingest] Found {len(pdf_paths)} PDF(s) in '{data_dir}':")
        for p in pdf_paths:
            print(f"         - {p.name}")

    ingest([str(p) for p in pdf_paths], tenant_id=args.tenant_id)
