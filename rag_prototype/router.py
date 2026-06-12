"""
router.py — Intent-aware query router.

Given a question and a tenant_id, classifies the intent into one of:

    doc_rag            → semantic search over PDF docs  (ChromaDB rag_docs)
    product_rag        → semantic search over products  (ChromaDB products)
    analytics_newest   → newest_products() SQL query
    analytics_discount → highest_discount_products() SQL query
    analytics_demand   → highest_demand_products() SQL query

Classification order:
    1. Keyword fast-path (zero latency, covers the obvious cases)
    2. Ollama LLM with a tight classification prompt
    3. Default fallback → doc_rag

Entry point:
    ask(question, tenant_id, limit=5) -> str
"""

import json
import logging
import re
import urllib.request

import chromadb
from sentence_transformers import SentenceTransformer

import config
from query import ask_ollama, build_prompt, retrieve
from tools.analytics import (
    highest_demand_products,
    highest_discount_products,
    newest_products,
)

logger = logging.getLogger(__name__)

# ── Valid classification labels ───────────────────────────────────────────────

_LABELS = (
    "doc_rag",
    "product_rag",
    "analytics_newest",
    "analytics_discount",
    "analytics_demand",
)

# ── Keyword fast-path ─────────────────────────────────────────────────────────
# Ordered from most-specific to least-specific to avoid false matches.

_KEYWORD_MAP: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"\b(newest|latest|most recent|just added|recently added|new arrival"
            r"|recently launched|just launched)\b",
            re.I,
        ),
        "analytics_newest",
    ),
    (
        re.compile(
            r"\b(biggest discount|largest discount|highest discount|most discounted"
            r"|on sale|best deal|best price|cheapest|lowest price)\b",
            re.I,
        ),
        "analytics_discount",
    ),
    (
        re.compile(
            r"\b(highest demand|most popular|most demanded|top demand"
            r"|trending|best.?sell|popular|in demand)\b",
            re.I,
        ),
        "analytics_demand",
    ),
]

# ── LLM classification prompt ─────────────────────────────────────────────────

_CLASSIFY_PROMPT = """\
Classify the user question into exactly one label. Output ONLY the label, nothing else.

Labels:
  doc_rag            — company policy, contracts, terms, documentation, business rules
  product_rag        — product recommendation, description, comparison, or search
  analytics_newest   — newest / most recently added products
  analytics_discount — products with the biggest discounts or lowest prices
  analytics_demand   — most popular / highest-demand / best-selling products

Question: {question}
Label:"""

# ── Classification helpers ────────────────────────────────────────────────────


def _keyword_classify(question: str) -> str | None:
    for pattern, label in _KEYWORD_MAP:
        if pattern.search(question):
            return label
    return None


def _llm_classify(question: str) -> str | None:
    """Call Ollama with a tight classification prompt. Returns a valid label or None."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps(
        {
            "model": config.LLM_MODEL,
            "prompt": _CLASSIFY_PROMPT.format(question=question),
            "stream": False,
            "options": {"num_predict": 12},
            "keep_alive": config.LLM_KEEP_ALIVE,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode()).get("response", "").strip().lower()
            for label in _LABELS:
                if label in raw:
                    return label
    except Exception as exc:
        logger.warning("[router] LLM classify failed: %s", exc)
    return None


def classify_intent(question: str) -> str:
    """
    Return the intent label for *question*.
    Tries keyword patterns first, then LLM, then defaults to doc_rag.
    Always logs the chosen intent and the path that produced it.
    """
    label = _keyword_classify(question)
    if label:
        logger.info("[router] intent=%-20s  path=keyword   question=%r", label, question)
        print(f"[router] intent={label}  (keyword match)")
        return label

    label = _llm_classify(question)
    if label:
        logger.info("[router] intent=%-20s  path=llm        question=%r", label, question)
        print(f"[router] intent={label}  (LLM classification)")
        return label

    logger.info("[router] intent=doc_rag               path=default    question=%r", question)
    print("[router] intent=doc_rag  (default fallback)")
    return "doc_rag"


# ── Analytics answer synthesis ────────────────────────────────────────────────

_ANALYTICS_SYSTEM = (
    "You are a helpful assistant. Answer the user's question using ONLY the "
    "structured data provided below. Be concise and factual. Do not invent "
    "information that is not in the data."
)

_ANALYTICS_PROMPT = (
    "{system}\n\n"
    "=== DATA ===\n{data}\n\n"
    "=== QUESTION ===\n{question}\n\n"
    "=== ANSWER ==="
)


def _format_rows(rows: list[dict]) -> str:
    lines = []
    for i, p in enumerate(rows, 1):
        disc = f"  {p['discount_pct']:.0f}% off" if p["discount_pct"] else ""
        lines.append(
            f"{i}. {p['name']}"
            f"  |  ${p['price']:.2f}{disc}"
            f"  |  demand={p['demand_score']}"
            f"  |  stock={p['stock']}"
            f"  |  added={p['created_at'][:10] if p['created_at'] else 'unknown'}"
        )
    return "\n".join(lines)


def _analytics_answer(question: str, rows: list[dict]) -> str:
    if not rows:
        return "No products found for that query."
    prompt = _ANALYTICS_PROMPT.format(
        system=_ANALYTICS_SYSTEM,
        data=_format_rows(rows),
        question=question,
    )
    answer, _ = ask_ollama(prompt)
    return answer


# ── RAG answer helpers ────────────────────────────────────────────────────────


def _rag_answer(
    question: str,
    tenant_id: int,
    model: SentenceTransformer,
    collection,
    collection_label: str,
) -> str:
    chunks, _, _, _, _ = retrieve(question, model, collection, tenant_id)
    if not chunks:
        return f"No relevant content found in {collection_label}."
    prompt = build_prompt(question, chunks[: config.MAX_CONTEXT_CHUNKS], tenant_id)
    answer, _ = ask_ollama(prompt)
    return answer


# ── Public entry point ────────────────────────────────────────────────────────


def ask(question: str, tenant_id: int, limit: int = 5) -> str:
    """
    Classify *question*, run the appropriate retrieval or SQL tool, and return
    a natural-language answer.  Prints the chosen intent so the caller can see
    which path was taken.
    """
    intent = classify_intent(question)

    # ── Analytics paths (SQL, no embeddings) ─────────────────────────────────
    if intent == "analytics_newest":
        rows = newest_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows)

    if intent == "analytics_discount":
        rows = highest_discount_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows)

    if intent == "analytics_demand":
        rows = highest_demand_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows)

    # ── RAG paths (embeddings + ChromaDB) ────────────────────────────────────
    model = SentenceTransformer(config.EMBED_MODEL)
    chroma = chromadb.PersistentClient(path=config.CHROMA_DIR)

    if intent == "product_rag":
        try:
            collection = chroma.get_collection("products")
        except Exception:
            return "Product index not found — run sync_products.py first."
        print("[router] path=product_rag  (ChromaDB products collection)")
        return _rag_answer(question, tenant_id, model, collection, "products")

    # doc_rag (default)
    try:
        collection = chroma.get_collection(config.COLLECTION_NAME)
    except Exception:
        return f"Document index not found — run ingest.py first."
    print(f"[router] path=doc_rag  (ChromaDB {config.COLLECTION_NAME} collection)")
    return _rag_answer(question, tenant_id, model, collection, "docs")


# ── CLI smoke-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Route a question through the query router")
    parser.add_argument("question", help="Question to route and answer")
    parser.add_argument("--tenant-id", type=int, required=True, metavar="N")
    parser.add_argument("--limit", type=int, default=5, metavar="N",
                        help="Max rows for analytics queries (default: 5)")
    args = parser.parse_args()

    print("─" * 80)
    answer = ask(args.question, args.tenant_id, args.limit)
    print("─" * 80)
    print("ANSWER:")
    print(answer)
    print("─" * 80)
