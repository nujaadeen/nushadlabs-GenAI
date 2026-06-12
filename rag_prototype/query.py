"""
query.py — Embed a question, retrieve top-k chunks, build a prompt, ask Ollama.

Usage:
    python query.py "What products does the company sell?"
    python query.py          ← drops into an interactive REPL
"""

import argparse
import json
import re
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
# Compound question splitting
# ---------------------------------------------------------------------------

# Conjunctions that signal a question contains multiple sub-questions
_SPLIT_PATTERN = re.compile(
    r"\s+(?:and|also|additionally|as well as|plus|furthermore)\s+",
    re.IGNORECASE,
)


def split_compound_question(question: str) -> list[str]:
    """
    If a question contains clear coordinating conjunctions that join two
    self-contained sub-questions, split and return each part.  Otherwise
    returns the original question as a single-element list.

    We only split when both sides look question-like (contain a verb or
    question word) to avoid false positives on "A and B" noun phrases.
    """
    parts = _SPLIT_PATTERN.split(question)
    if len(parts) == 1:
        return [question]

    # Heuristic: each part should contain a verb or look like a question
    _looks_like_question = re.compile(
        r"\b(is|are|was|were|has|have|how|what|who|when|where|why|does|do|did|can|could|tell)\b",
        re.IGNORECASE,
    )
    valid_parts = [p.strip() for p in parts if p.strip() and _looks_like_question.search(p)]
    if len(valid_parts) < 2:
        return [question]

    print(f"[query] Compound question detected — splitting into {len(valid_parts)} sub-queries:")
    for i, p in enumerate(valid_parts, 1):
        print(f"        [{i}] {p}")
    return valid_parts


# ---------------------------------------------------------------------------
# ChromaDB retrieval
# ---------------------------------------------------------------------------

def retrieve(question: str, model: SentenceTransformer, collection) -> tuple[list[str], list[float], list[dict], float, float]:
    """
    Embed `question` (with BGE query instruction prefix), query ChromaDB for
    top-k results.  Returns (chunks, distances, metadatas, embed_ms, search_ms).
    """
    # BGE-small retrieves better when the QUERY is prefixed with this instruction.
    # Document embeddings stored in ChromaDB do NOT use this prefix.
    instructed_query = config.BGE_QUERY_INSTRUCTION + question

    t0 = time.perf_counter()
    q_embedding = model.encode([instructed_query], normalize_embeddings=True)
    embed_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    results = collection.query(
        query_embeddings=q_embedding.tolist(),
        n_results=config.TOP_K,
        include=["documents", "distances", "metadatas"],
    )
    search_ms = (time.perf_counter() - t1) * 1000

    chunks = results["documents"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    return chunks, distances, metadatas, embed_ms, search_ms


def retrieve_multi(sub_questions: list[str], model: SentenceTransformer, collection) -> tuple[list[str], list[float], list[dict], float, float]:
    """
    Retrieve chunks for each sub-question, merge, and de-duplicate by chunk ID.
    Returns the same shape as retrieve().
    """
    seen_docs: dict[str, tuple[float, dict]] = {}  # doc_text → (best_distance, meta)
    total_embed_ms = 0.0
    total_search_ms = 0.0

    for sub_q in sub_questions:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve(sub_q, model, collection)
        total_embed_ms += embed_ms
        total_search_ms += search_ms
        for chunk, dist, meta in zip(chunks, distances, metadatas):
            if chunk not in seen_docs or dist < seen_docs[chunk][0]:
                seen_docs[chunk] = (dist, meta)

    # Sort merged results by distance (best first)
    sorted_items = sorted(seen_docs.items(), key=lambda x: x[1][0])
    merged_chunks = [item[0] for item in sorted_items]
    merged_distances = [item[1][0] for item in sorted_items]
    merged_metadatas = [item[1][1] for item in sorted_items]
    return merged_chunks, merged_distances, merged_metadatas, total_embed_ms, total_search_ms


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a knowledgeable assistant for NovaSpark Technologies. "
    "Answer the user's question using ONLY the context provided below.\n"
    "When the user describes a business need or data challenge, explicitly recommend "
    "the most relevant NovaSpark product from the context and explain WHY it fits — "
    "do not hedge with 'it depends' when the context makes a clear recommendation possible.\n"
    "If the context genuinely does not contain enough information to answer, say so honestly."
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

def ask_ollama(prompt: str) -> tuple[str, float]:
    """Call Ollama's /api/generate endpoint.  Returns (response_text, llm_ms)."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": config.LLM_NUM_PREDICT,
        },
        "keep_alive": config.LLM_KEEP_ALIVE,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode())
            llm_ms = (time.perf_counter() - t0) * 1000
            return data.get("response", "").strip(), llm_ms
    except urllib.error.URLError as e:
        llm_ms = (time.perf_counter() - t0) * 1000
        msg = (
            f"[ERROR] Could not reach Ollama at {config.OLLAMA_BASE_URL}.\n"
            f"        Make sure Ollama is running (`ollama serve`) and the model is "
            f"pulled (`ollama pull {config.LLM_MODEL}`).\n"
            f"        Details: {e}"
        )
        return msg, llm_ms


# ---------------------------------------------------------------------------
# Single question handler
# ---------------------------------------------------------------------------

def answer_question(question: str, model: SentenceTransformer, collection) -> None:
    _hr("═")
    print(f"QUESTION: {question}")
    _hr("═")
    wall_start = time.perf_counter()

    # --- Compound question splitting ---
    sub_questions = split_compound_question(question)
    is_compound = len(sub_questions) > 1

    # --- Retrieval (with timing) ---
    if is_compound:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve_multi(sub_questions, model, collection)
    else:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve(question, model, collection)

    print(f"\n{'─'*_WRAP}")
    print(f"RETRIEVED CHUNKS  (cosine distance — LOWER is more similar; 0.0 = identical)")
    if is_compound:
        print(f"[merged results from {len(sub_questions)} sub-queries, de-duplicated]")
    print(f"{'─'*_WRAP}")
    for i, (chunk, dist, meta) in enumerate(zip(chunks, distances, metadatas)):
        similarity = 1.0 - dist
        print(f"\n[Chunk {i+1}]  distance={dist:.4f}  (similarity≈{similarity:.4f})  "
              f"source={meta.get('source','?')}  index={meta.get('chunk_index','?')}")
        print("─" * 40)
        for line in chunk.split("\n"):
            print(textwrap.fill(line, width=_WRAP) if line.strip() else "")

    # --- Prompt ---
    prompt = build_prompt(question, chunks)
    print(f"\n{'─'*_WRAP}")
    print("PROMPT SENT TO LLM")
    print(f"{'─'*_WRAP}")
    print(prompt)

    # --- LLM answer (with timing) ---
    print(f"\n{'─'*_WRAP}")
    print(f"LLM ANSWER  (model: {config.LLM_MODEL})")
    print(f"{'─'*_WRAP}")
    answer, llm_ms = ask_ollama(prompt)
    print(answer)

    # --- Timing breakdown ---
    total_ms = (time.perf_counter() - wall_start) * 1000
    print(f"\n{'─'*_WRAP}")
    print(f"TIMING BREAKDOWN")
    print(f"  Query embedding : {embed_ms:7.1f} ms")
    print(f"  Vector search   : {search_ms:7.1f} ms")
    print(f"  LLM generation  : {llm_ms:7.1f} ms  ← bottleneck")
    print(f"  Total (wall)    : {total_ms:7.1f} ms  ({total_ms/1000:.2f}s)")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Query the local RAG system")
    parser.add_argument("question", nargs="?", default=None, help="Question to ask")
    args = parser.parse_args()

    # Load model (kept warm; not reloaded between questions in interactive mode)
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
