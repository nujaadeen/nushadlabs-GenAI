"""
query.py — Embed a question, retrieve top-k chunks, build a prompt, ask Ollama.

Usage:
    python query.py "What products does the company sell?"
    python query.py          ← drops into an interactive REPL
"""

import argparse
import json
import re
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

import chromadb
from sentence_transformers import SentenceTransformer

from rag_agent import config

# Width for printing long text blocks
_WRAP = 100


def _hr(char="─", width=_WRAP):
    print(char * width)


# ---------------------------------------------------------------------------
# Ollama device detection
# ---------------------------------------------------------------------------

def get_ollama_device() -> str:
    """Return a one-line string describing whether Ollama is using GPU or CPU."""
    # Primary: Ollama /api/ps JSON endpoint (available since Ollama 0.1.33)
    try:
        url = f"{config.OLLAMA_BASE_URL}/api/ps"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            model_base = config.LLM_MODEL.split(":")[0]
            for m in data.get("models", []):
                if model_base in m.get("name", ""):
                    size_vram = m.get("size_vram", 0)
                    if size_vram and size_vram > 0:
                        return f"GPU ({size_vram / 1e9:.1f} GB VRAM)"
                    return "CPU (0 VRAM allocated)"
            return "CPU/GPU unknown (model not yet loaded — will show after first query)"
    except Exception:
        pass

    # Fallback: parse `ollama ps` CLI output
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=5
        )
        model_base = config.LLM_MODEL.split(":")[0]
        for line in result.stdout.splitlines()[1:]:
            if model_base in line:
                return "GPU" if "GPU" in line else "CPU"
        return "CPU/GPU unknown (model not yet loaded — will show after first query)"
    except Exception as exc:
        return f"unknown (could not query Ollama: {exc})"


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

def retrieve(
    question: str,
    model: SentenceTransformer,
    collection,
    tenant_id: int,
    n_results: int | None = None,
) -> tuple[list[str], list[float], list[dict], float, float]:
    """
    Embed `question` (with BGE query instruction prefix), query ChromaDB for
    n_results (defaults to TOP_K).  Returns (chunks, distances, metadatas, embed_ms, search_ms).

    Every query is hard-filtered to tenant_id — there is no code path that
    queries without this filter.
    """
    if n_results is None:
        n_results = config.TOP_K

    # BGE models require a query instruction prefix; other models do not.
    prefix = config.BGE_QUERY_INSTRUCTION if "bge" in config.EMBED_MODEL.lower() else ""
    instructed_query = prefix + question

    t0 = time.perf_counter()
    q_embedding = model.encode([instructed_query], normalize_embeddings=True)
    embed_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    results = collection.query(
        query_embeddings=q_embedding.tolist(),
        n_results=n_results,
        where={"tenant_id": tenant_id},
        include=["documents", "distances", "metadatas"],
    )
    search_ms = (time.perf_counter() - t1) * 1000

    chunks = results["documents"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]
    return chunks, distances, metadatas, embed_ms, search_ms


def retrieve_multi(
    sub_questions: list[str],
    model: SentenceTransformer,
    collection,
    tenant_id: int,
) -> tuple[list[str], list[float], list[dict], float, float]:
    """
    Retrieve top-3 chunks per sub-question, merge, and de-duplicate by chunk text.
    Returns the same shape as retrieve().
    """
    seen_docs: dict[str, tuple[float, dict]] = {}  # doc_text → (best_distance, meta)
    total_embed_ms = 0.0
    total_search_ms = 0.0

    for sub_q in sub_questions:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve(
            sub_q, model, collection, tenant_id, n_results=config.COMPOUND_K
        )
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

def _build_system_prompt(tenant_id: int | None) -> str:
    tenant = config.TENANT_REGISTRY.get(tenant_id) if tenant_id is not None else None
    if tenant:
        intro = f"You are a knowledgeable assistant for {tenant['name']}, {tenant['description']}."
    else:
        intro = "You are a knowledgeable assistant."

    return (
        f"{intro} "
        "Answer the user's question using ONLY the context provided below. "
        "Keep your answer concise.\n\n"
        "CITATION RULE: For every factual claim that involves a specific number, name, or date, "
        "you MUST quote the exact sentence from the context that supports it, in the form: "
        "Answer ... (source: \"<exact quoted sentence from context>\"). "
        "If no sentence in the context states the fact, say exactly: "
        "\"I cannot find that information in the provided context.\" "
        "Do NOT infer, estimate, or guess numbers — only report what the context explicitly states.\n\n"
        "When the user describes a need, explicitly recommend the most relevant product or service "
        "from the context and explain WHY it fits — "
        "do not hedge with 'it depends' when the context makes a clear recommendation possible.\n"
        "If the context genuinely does not contain enough information to answer, say so honestly."
    )


def build_prompt(question: str, chunks: list[str], tenant_id: int | None = None) -> str:
    context_block = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)
    )
    return (
        f"{_build_system_prompt(tenant_id)}\n\n"
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


def ask_ollama_stream(prompt: str) -> Iterator[str]:
    """Stream tokens from Ollama's /api/generate endpoint one by one."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": config.LLM_NUM_PREDICT},
        "keep_alive": config.LLM_KEEP_ALIVE,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line.decode())
                except json.JSONDecodeError:
                    continue
                token = data.get("response", "")
                if token:
                    yield token
                if data.get("done"):
                    break
    except urllib.error.URLError as e:
        yield f"[ERROR] Could not reach Ollama at {config.OLLAMA_BASE_URL}: {e}"


# ---------------------------------------------------------------------------
# Single question handler
# ---------------------------------------------------------------------------

def answer_question(question: str, model: SentenceTransformer, collection, tenant_id: int) -> None:
    _hr("═")
    print(f"QUESTION: {question}")
    _hr("═")
    wall_start = time.perf_counter()

    # --- Compound question splitting ---
    sub_questions = split_compound_question(question)
    is_compound = len(sub_questions) > 1

    # --- Retrieval (with timing) ---
    if is_compound:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve_multi(sub_questions, model, collection, tenant_id)
    else:
        chunks, distances, metadatas, embed_ms, search_ms = retrieve(question, model, collection, tenant_id)

    retrieved_count = len(chunks)

    if retrieved_count == 0:
        print(
            f"\n[query] WARNING: 0 chunks found for tenant_id='{tenant_id}'.\n"
            f"         Possible causes:\n"
            f"           1. Tenant ID mismatch — ingest used a different ID "
            f"(e.g. 'tenant_2') than the one passed here ('{tenant_id}').\n"
            f"           2. No data has been ingested yet for this tenant.\n"
            f"         Fix: run  python ingest.py --tenant-id {tenant_id}"
        )
        return

    # Cap the context sent to the LLM (biggest single latency and grounding win).
    chunks    = chunks[:config.MAX_CONTEXT_CHUNKS]
    distances = distances[:config.MAX_CONTEXT_CHUNKS]
    metadatas = metadatas[:config.MAX_CONTEXT_CHUNKS]
    print(f"[query] Context: retrieved {retrieved_count} chunks → "
          f"sending {len(chunks)} to LLM (MAX_CONTEXT_CHUNKS={config.MAX_CONTEXT_CHUNKS})")

    print(f"\n{'─'*_WRAP}")
    print(f"RETRIEVED CHUNKS  (cosine distance — LOWER is more similar; 0.0 = identical)")
    if is_compound:
        print(f"[{len(sub_questions)} sub-queries × {config.COMPOUND_K} each → "
              f"{retrieved_count} unique after dedup → {len(chunks)} sent to LLM]")
    print(f"{'─'*_WRAP}")
    for i, (chunk, dist, meta) in enumerate(zip(chunks, distances, metadatas)):
        similarity = 1.0 - dist
        print(f"\n[Chunk {i+1}]  distance={dist:.4f}  (similarity≈{similarity:.4f})  "
              f"source={meta.get('source','?')}  index={meta.get('chunk_index','?')}")
        print("─" * 40)
        for line in chunk.split("\n"):
            print(textwrap.fill(line, width=_WRAP) if line.strip() else "")

    # --- Prompt ---
    prompt = build_prompt(question, chunks, tenant_id)
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
    parser = argparse.ArgumentParser(
        description="Query the local RAG system",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("question", nargs="?", default=None, help="Question to ask")
    parser.add_argument("--tenant-id", required=True, type=int, metavar="N",
                        help="Tenant identifier (positive integer) — restricts retrieval to this tenant's data only")
    parser.add_argument("--top-k", type=int, default=None, metavar="N",
                        help=f"Chunks to retrieve (config default: {config.TOP_K})")
    parser.add_argument("--max-context-chunks", type=int, default=None, metavar="N",
                        help=f"Chunks sent to LLM (config default: {config.MAX_CONTEXT_CHUNKS})")
    parser.add_argument("--embed-model", default=None, metavar="MODEL",
                        help=f"Embedding model — must match what was used in ingest (config default: {config.EMBED_MODEL})")
    args = parser.parse_args()

    # Apply CLI overrides in-process (does NOT edit config.py)
    if args.top_k is not None:
        config.TOP_K = args.top_k
    if args.max_context_chunks is not None:
        config.MAX_CONTEXT_CHUNKS = args.max_context_chunks
    if args.embed_model is not None:
        config.EMBED_MODEL = args.embed_model

    # Load model (kept warm; not reloaded between questions in interactive mode)
    print(f"[query] Loading embedding model '{config.EMBED_MODEL}' …")
    model = SentenceTransformer(config.EMBED_MODEL)

    # Report Ollama hardware before the first query
    device = get_ollama_device()
    print(f"[query] Ollama serving '{config.LLM_MODEL}' on: {device}")

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    try:
        collection = client.get_collection(config.COLLECTION_DOCS)
        print(f"[query] Connected to collection '{config.COLLECTION_DOCS}' "
              f"({collection.count()} chunks).\n")
    except Exception:
        print(f"[query] ERROR: Collection '{config.COLLECTION_DOCS}' not found.")
        print(f"         Run `python ingest.py --tenant-id TENANT_ID` first.")
        sys.exit(1)

    if args.question:
        answer_question(args.question, model, collection, tenant_id=args.tenant_id)
    else:
        print("Interactive mode — type your question and press Enter. Ctrl-C to quit.\n")
        try:
            while True:
                q = input("Question> ").strip()
                if q:
                    answer_question(q, model, collection, tenant_id=args.tenant_id)
        except (KeyboardInterrupt, EOFError):
            print("\n[query] Bye.")


if __name__ == "__main__":
    main()
