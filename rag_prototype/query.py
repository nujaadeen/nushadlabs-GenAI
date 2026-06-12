"""
query.py — Embed a question, retrieve top-k chunks, build a prompt, ask Ollama.

Usage:
    python query.py "What products does the company sell?"
    python query.py          ← drops into an interactive REPL
"""

import argparse
import json
import sys
import textwrap
import time
import urllib.request

import chromadb
from sentence_transformers import SentenceTransformer

import config

# Width for printing long text blocks
_WRAP = 100


def _hr(char="─", width=_WRAP):
    print(char * width)


# ---------------------------------------------------------------------------
# ChromaDB retrieval
# ---------------------------------------------------------------------------

def retrieve(question: str, model: SentenceTransformer, collection) -> dict:
    """
    Embed `question`, query ChromaDB for top-k results.
    Returns the raw ChromaDB query result dict.
    """
    q_embedding = model.encode([question], normalize_embeddings=True)
    results = collection.query(
        query_embeddings=q_embedding.tolist(),
        n_results=config.TOP_K,
        include=["documents", "distances", "metadatas"],
    )
    return results


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using ONLY the context "
    "provided below. If the context does not contain enough information, say so clearly "
    "rather than guessing."
)


def build_prompt(question: str, chunks: list[str]) -> str:
    context_block = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)
    )
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== CONTEXT ===\n{context_block}\n\n"
        f"=== QUESTION ===\n{question}\n\n"
        f"=== ANSWER ==="
    )


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def ask_ollama(prompt: str) -> str:
    """Call Ollama's /api/generate endpoint and return the full response text."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        return (
            f"[ERROR] Could not reach Ollama at {config.OLLAMA_BASE_URL}.\n"
            f"        Make sure Ollama is running (`ollama serve`) and the model is "
            f"pulled (`ollama pull {config.LLM_MODEL}`).\n"
            f"        Details: {e}"
        )


# ---------------------------------------------------------------------------
# Single question handler
# ---------------------------------------------------------------------------

def answer_question(question: str, model: SentenceTransformer, collection) -> None:
    _hr("═")
    print(f"QUESTION: {question}")
    _hr("═")
    _start = time.perf_counter()

    # --- Retrieval ---
    results = retrieve(question, model, collection)
    chunks = results["documents"][0]       # list of chunk texts
    distances = results["distances"][0]    # ChromaDB cosine distances (lower = closer)
    metadatas = results["metadatas"][0]

    print(f"\n{'─'*_WRAP}")
    print(f"RETRIEVED CHUNKS  (cosine distance — LOWER is more similar; 0.0 = identical)")
    print(f"{'─'*_WRAP}")
    for i, (chunk, dist, meta) in enumerate(zip(chunks, distances, metadatas)):
        similarity = 1.0 - dist   # convert distance → similarity for intuition
        print(f"\n[Chunk {i+1}]  distance={dist:.4f}  (similarity≈{similarity:.4f})  "
              f"source={meta.get('source','?')}  index={meta.get('chunk_index','?')}")
        print("─" * 40)
        # Wrap long chunks for readability
        for line in chunk.split("\n"):
            print(textwrap.fill(line, width=_WRAP) if line.strip() else "")

    # --- Prompt ---
    prompt = build_prompt(question, chunks)
    print(f"\n{'─'*_WRAP}")
    print("PROMPT SENT TO LLM")
    print(f"{'─'*_WRAP}")
    print(prompt)

    # --- LLM answer ---
    print(f"\n{'─'*_WRAP}")
    print(f"LLM ANSWER  (model: {config.LLM_MODEL})")
    print(f"{'─'*_WRAP}")
    answer = ask_ollama(prompt)
    print(answer)
    print(f"\n[Elapsed: {time.perf_counter() - _start:.2f}s]")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Query the local RAG system")
    parser.add_argument("question", nargs="?", default=None, help="Question to ask")
    args = parser.parse_args()

    # Load model
    print(f"[query] Loading embedding model '{config.EMBED_MODEL}' …")
    model = SentenceTransformer(config.EMBED_MODEL)

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    try:
        collection = client.get_collection(config.COLLECTION_NAME)
        print(f"[query] Connected to collection '{config.COLLECTION_NAME}' "
              f"({collection.count()} chunks).\n")
    except Exception:
        print(f"[query] ERROR: Collection '{config.COLLECTION_NAME}' not found.")
        print(f"         Run `python ingest.py` first.")
        sys.exit(1)

    if args.question:
        answer_question(args.question, model, collection)
    else:
        print("Interactive mode — type your question and press Enter. Ctrl-C to quit.\n")
        try:
            while True:
                q = input("Question> ").strip()
                if q:
                    answer_question(q, model, collection)
        except (KeyboardInterrupt, EOFError):
            print("\n[query] Bye.")


if __name__ == "__main__":
    main()
