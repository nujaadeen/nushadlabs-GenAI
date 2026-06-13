"""
router.py — Intent-aware query router (hybrid front door).

Classifies a question into one of:

    doc_rag            → semantic search over PDF docs  (ChromaDB rag_docs)
    product_rag        → semantic search over products  (ChromaDB products)
    product_lookup     → precise field (stock/price) for a NAMED product — SQL only
    analytics_newest   → newest_products() SQL query
    analytics_discount → highest_discount_products() SQL query
    analytics_demand   → highest_demand_products() SQL query
    agent              → multi-step question; escalated to agent_stream

Classification order:
    1. Multi-step heuristic  (zero latency, catches compound/compare questions)
    2. Single-shot keyword patterns  (zero latency, existing analytics signals)
    3. Ollama LLM classifier  (tight prompt, num_predict=12)
    4. Default fallback → doc_rag

Routing is controlled by config.ROUTER_MODE:
    "hybrid"  — this file is the front door; escalates to agent on "agent" intent
    "router"  — never escalates; "agent" falls back to product_rag
    "agent"   — bypasses classification; everything goes straight to agent_stream

Entry points:
    ask(question, tenant_id, limit=5) -> str          (blocking, CLI)
    ask_stream(question, tenant_id, ...)  -> Iterator  (SSE, used by api.py)
"""

import json
import logging
import re
import time
import urllib.request
from collections.abc import Iterator

import chromadb
from sentence_transformers import SentenceTransformer

from rag_agent import config
from rag_agent.retrieval.query import ask_ollama, ask_ollama_stream, retrieve
from rag_agent.tools.analytics import (
    find_products_by_name,
    highest_demand_products,
    highest_discount_products,
    newest_products,
)

logger = logging.getLogger(__name__)

# ── Valid classification labels ───────────────────────────────────────────────

_LABELS = (
    "doc_rag",
    "product_rag",
    "product_lookup",
    "analytics_newest",
    "analytics_discount",
    "analytics_demand",
    "agent",
)

# ── Product-lookup heuristic (checked FIRST — highest specificity) ────────────
# Matches questions asking for a PRECISE FIELD (stock / price) of a NAMED product.
# Returns "product_lookup" when a name is extractable, "agent" when field cues
# are present but the name is unclear (to avoid falling through to product_rag).

_FIELD_CUE_PATTERN = re.compile(
    r'\b(?:how\s+many|how\s+much|price\s+of|cost\s+of|stock\s+of|quantity\s+of|in\s+stock)\b',
    re.I,
)

# Ordered from most-specific to least-specific; first match wins.
_NAME_EXTRACT_PATTERNS = [
    re.compile(r'\bhow\s+many\s+(.+?)\s+(?:are|is)\s+(?:in\s*stock|left|there)\b', re.I),
    re.compile(r'\bhow\s+many\s+(.+?)(?:\s+(?:do|does|are|is)\b|\s*\?|$)', re.I),
    re.compile(r'\bhow\s+much\s+does\s+(.+?)\s+cost\b', re.I),
    re.compile(r'\bhow\s+much\s+(.+?)\s+(?:do\s+(?:we|you)\s+have|is\s+left|is\s+in\s+stock)\b', re.I),
    re.compile(r'\b(?:price|cost)\s+of\s+(.+?)(?:\s*\?|$)', re.I),
    re.compile(r'\b(?:stock|quantity)\s+of\s+(.+?)(?:\s*\?|$)', re.I),
    re.compile(r'\b(?:is|are)\s+(.+?)\s+in\s*stock\b', re.I),
    re.compile(r'\bwhat\s+(?:is|are)\s+(?:the\s+)?(?:price|cost|stock|quantity)\s+(?:of|for)\s+(.+?)(?:\s*\?|$)', re.I),
    re.compile(r'^(.+?)\s+in\s*stock\s*\??$', re.I),
]

# Trailing noise to strip from a captured name
_NAME_CLEANUP = re.compile(r'\s+(?:please|now|today)\s*$', re.I)


def _extract_product_name(question: str) -> str | None:
    """Try to extract a product name from a field-query question. Returns None if unclear."""
    for pattern in _NAME_EXTRACT_PATTERNS:
        m = pattern.search(question)
        if m:
            name = m.group(1).strip().rstrip('?').strip()
            name = _NAME_CLEANUP.sub('', name).strip()
            if len(name) > 2:
                return name
    return None


def _product_lookup_classify(question: str) -> str | None:
    """Return 'product_lookup' when a field + name are clear, 'agent' when
    field cues exist but the product name is ambiguous, None if no field cues."""
    if not _FIELD_CUE_PATTERN.search(question):
        return None
    name = _extract_product_name(question)
    if name:
        return "product_lookup"
    # Field cues present but name unclear → agent handles it via get_product_by_id
    return "agent"


# ── Multi-step heuristic (checked before single-shot keyword patterns) ────────
# Conservative — fires only on clear compound/compare signals.
# When unsure, we do NOT match here; LLM classify or single-shot keyword wins.

_MULTISTEP_PATTERN = re.compile(
    # explicit comparison request
    r"\bcompare\b"
    # "of the/our/my X … which …" — cross-list reasoning
    r"|of\s+(?:the|our|my|your|those|them|these)\b.{1,60}?\bwhich\b"
    # two distinct actions joined by "and": "find a laptop and tell me its discount"
    r"|\band\b.{0,50}\b(?:tell|give|compare|check|rank|sort|which\s+is|what\s+is|how\s+(?:much|many))\b"
    # sequential steps: "… then find / show / compare …"
    r"|\bthen\b.{0,40}\b(?:find|get|show|tell|give|compare|check|rank|sort)\b"
    # "both … product/price/…" — dual-item questions
    r"|\bboth\b.{0,60}\b(?:product|item|price|stock|discount|newest|latest|popular|demand)\b",
    re.I,
)


def _multistep_classify(question: str) -> str | None:
    """Return 'agent' if the question contains obvious multi-step cues, else None."""
    if _MULTISTEP_PATTERN.search(question):
        return "agent"
    return None


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
  product_lookup     — stock count, price, or availability of a SPECIFIC NAMED product,
                       e.g. "how many Organic Baby Spinach are in stock", "price of Fresh Milk"
  doc_rag            — company policy, contracts, terms, documentation, business rules
  product_rag        — product recommendation, description, comparison, or search
  analytics_newest   — newest / most recently added products
  analytics_discount — products with the biggest discounts or lowest prices
  analytics_demand   — most popular / highest-demand / best-selling products
  agent              — questions needing MORE THAN ONE lookup, e.g. "of the newest
                       products which is cheapest", "compare product 12 and 30",
                       "find a laptop and tell me its discount"

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

    Order:
      1. Product-lookup heuristic → "product_lookup" / "agent"  (highest specificity)
      2. Multi-step heuristic     → "agent"  (conservative; compound cues only)
      3. Single-shot keywords     → analytics_* labels
      4. LLM classifier           → any label including "agent"
      5. Default                  → "doc_rag"
    """
    label = _product_lookup_classify(question)
    if label:
        logger.info("[router] intent=%-20s  path=product_lookup_heuristic  question=%r", label, question)
        print(f"[router] intent={label}  (product-lookup heuristic)")
        return label

    label = _multistep_classify(question)
    if label:
        logger.info("[router] intent=%-20s  path=multistep  question=%r", label, question)
        print(f"[router] intent={label}  (multi-step heuristic)")
        return label

    label = _keyword_classify(question)
    if label:
        logger.info("[router] intent=%-20s  path=keyword    question=%r", label, question)
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


# ── Polite no-answer message ──────────────────────────────────────────────────

# Phrases the LLM may produce when the context doesn't cover the question.
_LLM_NO_ANSWER_PATTERNS = re.compile(
    r"(cannot find that information|not in the provided context"
    r"|i (don't|do not|couldn't|could not) (have|find)|unable to (find|answer)"
    r"|no information (in|from|about)|not (enough|sufficient) information"
    r"|i am not able to|the context (does not|doesn't) (contain|include|mention))",
    re.I,
)


def _no_answer_msg(tenant_id: int) -> str:
    """Return a polite fallback message, personalised with the tenant name if known."""
    tenant = config.TENANT_REGISTRY.get(tenant_id)
    name = f" at {tenant['name']}" if tenant else ""
    return (
        f"I'm sorry, I wasn't able to find any information regarding your inquiry{name}. "
        "For further assistance, please contact our customer care team or send your "
        "enquiry via email and we'll be happy to help you."
    )


# ── Product-lookup formatting (Python-only, no LLM) ──────────────────────────


def _format_product_lookup_answer(rows: list[dict]) -> str:
    """Format ILIKE product-lookup results as plain text — no LLM."""
    if not rows:
        return ""
    if len(rows) == 1:
        p = rows[0]
        date = p["created_at"][:10] if p["created_at"] else "unknown"
        disc = f", {p['discount_pct']:.0f}% off" if p["discount_pct"] else ""
        return (
            f"{p['name']}: ${p['price']:.2f}{disc}, "
            f"{p['stock']} in stock, added {date}."
        )
    lines = [f"Found {len(rows)} matching products:"]
    for i, p in enumerate(rows, 1):
        date = p["created_at"][:10] if p["created_at"] else "unknown"
        disc = f", {p['discount_pct']:.0f}% off" if p["discount_pct"] else ""
        lines.append(
            f"{i}. {p['name']} — ${p['price']:.2f}{disc},"
            f" {p['stock']} in stock, added {date}"
        )
    return "\n".join(lines)


# ── Analytics formatting (Python-only, no LLM) ───────────────────────────────

_ANALYTICS_HEADERS = {
    "analytics_newest":   "Here are the {n} newest products:",
    "analytics_discount": "Here are the {n} most discounted products:",
    "analytics_demand":   "Here are the {n} most popular products:",
}


def _format_analytics_answer(intent: str, rows: list[dict]) -> str:
    """Build a clean numbered list directly from SQL rows — zero LLM involvement."""
    header = _ANALYTICS_HEADERS.get(intent, "Here are {n} products:").format(n=len(rows))
    lines = [header]
    for i, p in enumerate(rows, 1):
        date = p["created_at"][:10] if p["created_at"] else "unknown"
        disc = f", {p['discount_pct']:.0f}% off" if p["discount_pct"] else ""
        lines.append(
            f"{i}. {p['name']} — ${p['price']:.2f}{disc},"
            f" added {date}, {p['stock']} in stock"
        )
    return "\n".join(lines)


# ── Optional one-line LLM intro (ANALYTICS_LLM_INTRO=True only) ─────────────

_ANALYTICS_INTRO_PROMPT = (
    "Write ONE short sentence introducing a product list to the user. "
    "Do not list or describe the products yourself.\n"
    "Question: {question}\n"
    "Number of results: {count}\n"
    "Intro:"
)


def _analytics_intro_sentence(question: str, count: int) -> str:
    """Return a single LLM-generated intro sentence, or '' on failure."""
    url = f"{config.OLLAMA_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "prompt": _ANALYTICS_INTRO_PROMPT.format(question=question, count=count),
        "stream": False,
        "options": {"num_predict": 50},
        "keep_alive": config.LLM_KEEP_ALIVE,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode()).get("response", "").strip()
    except Exception as exc:
        logger.warning("[analytics] LLM intro failed: %s", exc)
        return ""


# ── Non-streaming analytics (used by ask()) ───────────────────────────────────

def _analytics_answer(question: str, rows: list[dict], intent: str, tenant_id: int) -> str:
    if not rows:
        return _no_answer_msg(tenant_id)
    formatted = _format_analytics_answer(intent, rows)
    if config.ANALYTICS_LLM_INTRO:
        intro = _analytics_intro_sentence(question, len(rows))
        return f"{intro}\n\n{formatted}" if intro else formatted
    return formatted


# ── RAG system prompt (router variant) ───────────────────────────────────────
# Overrides the "say so honestly" line from query.build_prompt so the LLM
# produces the polite redirect instead of a blunt "I cannot find" reply.

def _rag_system_prompt(tenant_id: int) -> str:
    tenant = config.TENANT_REGISTRY.get(tenant_id)
    if tenant:
        intro = f"You are a knowledgeable assistant for {tenant['name']}, {tenant['description']}."
    else:
        intro = "You are a knowledgeable assistant."
    no_answer = _no_answer_msg(tenant_id)
    return (
        f"{intro} "
        "Answer the user's question using ONLY the context provided below. "
        "Answer in plain prose. "
        "Do NOT mention chunk numbers, do NOT output any (source: ...) string, "
        "and do NOT include angle-bracket placeholders. "
        "Keep your answer concise.\n\n"
        f"If the context does not contain enough information to answer, reply with exactly:\n"
        f"\"{no_answer}\"\n"
        "Do NOT infer, estimate, or guess — only report what the context explicitly states."
    )


def _history_block(history: list[dict] | None) -> str:
    if not history:
        return ""
    recent = history[-4:]  # last 2 user+assistant pairs
    lines = ["=== CONVERSATION HISTORY ==="]
    for turn in recent:
        lines.append(f"{turn['role'].capitalize()}: {turn['content']}")
    return "\n".join(lines) + "\n\n"


def _build_rag_prompt(
    question: str,
    chunks: list[str],
    tenant_id: int,
    history: list[dict] | None = None,
) -> str:
    context_block = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(chunks)
    )
    return (
        f"{_rag_system_prompt(tenant_id)}\n\n"
        f"{_history_block(history)}"
        f"=== CONTEXT ===\n{context_block}\n\n"
        f"=== QUESTION ===\n{question}\n\n"
        f"=== ANSWER ==="
    )


# ── RAG answer helpers ────────────────────────────────────────────────────────


def _rag_answer(
    question: str,
    tenant_id: int,
    model: SentenceTransformer,
    collection,
) -> str:
    chunks, _, _, _, _ = retrieve(question, model, collection, tenant_id)
    if not chunks:
        return _no_answer_msg(tenant_id)
    prompt = _build_rag_prompt(question, chunks[: config.MAX_CONTEXT_CHUNKS], tenant_id)
    answer, _ = ask_ollama(prompt)
    # Guard: if the LLM still produces a "cannot find" variant, swap for the
    # polite message so the response is always consistent.
    if _LLM_NO_ANSWER_PATTERNS.search(answer):
        return _no_answer_msg(tenant_id)
    return answer


# ── Public entry point ────────────────────────────────────────────────────────


def ask(question: str, tenant_id: int, limit: int = 5) -> str:
    """
    Classify *question*, run the appropriate retrieval or SQL tool, and return
    a natural-language answer.  Prints the chosen intent so the caller can see
    which path was taken.
    """
    from rag_agent.retrieval.agent import agent_stream  # local import avoids a potential circular ref

    intent = "agent" if config.ROUTER_MODE == "agent" else classify_intent(question)

    # ── Agent path ────────────────────────────────────────────────────────────
    if intent == "agent":
        if config.ROUTER_MODE in ("hybrid", "agent"):
            print("[router] intent=agent → running agent_stream (CLI collect mode)")
            model = SentenceTransformer(config.EMBED_MODEL)
            chroma = chromadb.PersistentClient(path=config.CHROMA_DIR)
            tokens = [
                chunk["content"]
                for chunk in agent_stream(question, tenant_id, model, chroma, limit=limit)
                if chunk["type"] == "token"
            ]
            return "".join(tokens)
        else:  # ROUTER_MODE="router" — fall back to product_rag
            intent = "product_rag"

    # ── Product-lookup path (SQL ILIKE, no embeddings) ───────────────────────
    if intent == "product_lookup":
        name = _extract_product_name(question) or question
        rows = find_products_by_name(tenant_id, name)
        print(f"[router] SQL product_lookup: name={name!r}, rows={len(rows)}")
        if not rows:
            return _no_answer_msg(tenant_id)
        return _format_product_lookup_answer(rows)

    # ── Analytics paths (SQL, no embeddings) ─────────────────────────────────
    if intent == "analytics_newest":
        rows = newest_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows, intent, tenant_id)

    if intent == "analytics_discount":
        rows = highest_discount_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows, intent, tenant_id)

    if intent == "analytics_demand":
        rows = highest_demand_products(tenant_id, limit)
        print(f"[router] SQL returned {len(rows)} row(s)")
        return _analytics_answer(question, rows, intent, tenant_id)

    # ── RAG paths (embeddings + ChromaDB) ────────────────────────────────────
    model = SentenceTransformer(config.EMBED_MODEL)
    chroma = chromadb.PersistentClient(path=config.CHROMA_DIR)

    if intent == "product_rag":
        try:
            collection = chroma.get_collection(config.COLLECTION_PRODUCTS)
        except Exception:
            return _no_answer_msg(tenant_id)
        print("[router] path=product_rag  (ChromaDB products collection)")
        return _rag_answer(question, tenant_id, model, collection)

    # doc_rag (default)
    try:
        collection = chroma.get_collection(config.COLLECTION_DOCS)
    except Exception:
        return _no_answer_msg(tenant_id)
    print(f"[router] path=doc_rag  (ChromaDB {config.COLLECTION_DOCS} collection)")
    return _rag_answer(question, tenant_id, model, collection)


# ── Streaming entry point (used by api.py) ────────────────────────────────────


def ask_stream(
    question: str,
    tenant_id: int,
    limit: int = 5,
    embed_model: SentenceTransformer | None = None,
    chroma_client: chromadb.PersistentClient | None = None,
    history: list[dict] | None = None,
) -> Iterator[dict]:
    """
    Classify *question*, run the appropriate tool, and yield streaming dicts:

        {"type": "token",  "content": "<text>"}  — one per Ollama output token
        {"type": "done",   "intent": "...", "sources": [...]}  — final event

    *embed_model* and *chroma_client* are optional; both are created lazily when
    not supplied (useful for CLI use; the API passes pre-loaded singletons).
    *history* is a list of {"role": "user"|"assistant", "content": str} from the
    session store; it is woven into the LLM prompt but NOT used for retrieval so
    that vector similarity is based on the current question only.
    """
    from rag_agent.retrieval.agent import agent_stream  # local import avoids a potential circular ref

    # ── ROUTER_MODE="agent" — bypass classification entirely ──────────────────
    if config.ROUTER_MODE == "agent":
        if embed_model is None:
            embed_model = SentenceTransformer(config.EMBED_MODEL)
        if chroma_client is None:
            chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
        yield from agent_stream(
            question, tenant_id,
            embed_model=embed_model,
            chroma_client=chroma_client,
            history=history,
            limit=limit,
        )
        return

    intent = classify_intent(question)

    # ── "agent" intent — escalate or fall back depending on ROUTER_MODE ───────
    if intent == "agent":
        if config.ROUTER_MODE == "hybrid":
            logger.info("[router] intent=agent → escalating to agent_stream")
            print("[router] intent=agent → escalating to agent_stream")
            if embed_model is None:
                embed_model = SentenceTransformer(config.EMBED_MODEL)
            if chroma_client is None:
                chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
            yield from agent_stream(
                question, tenant_id,
                embed_model=embed_model,
                chroma_client=chroma_client,
                history=history,
                limit=limit,
            )
            return
        else:  # ROUTER_MODE="router" — no escalation; treat as product_rag
            intent = "product_rag"

    # ── Product-lookup path (SQL ILIKE, no embeddings) ───────────────────────
    if intent == "product_lookup":
        name = _extract_product_name(question) or question
        logger.info("[router] product_lookup: name=%r", name)
        rows = find_products_by_name(tenant_id, name)
        sources = [{"type": "sql", "table": "products", "rows": len(rows)}]
        if not rows:
            yield {"type": "token", "content": _no_answer_msg(tenant_id)}
            yield {"type": "done", "intent": intent, "sources": []}
            return
        answer = _format_product_lookup_answer(rows)
        _CHUNK = 120
        for i in range(0, len(answer), _CHUNK):
            yield {"type": "token", "content": answer[i:i + _CHUNK]}
        yield {"type": "done", "intent": intent, "sources": sources}
        return

    # ── Analytics paths ───────────────────────────────────────────────────────
    if intent in ("analytics_newest", "analytics_discount", "analytics_demand"):
        t0 = time.monotonic()
        if intent == "analytics_newest":
            rows = newest_products(tenant_id, limit)
        elif intent == "analytics_discount":
            rows = highest_discount_products(tenant_id, limit)
        else:
            rows = highest_demand_products(tenant_id, limit)
        t_sql = time.monotonic()
        logger.info("[analytics] SQL: %.3fs, rows=%d", t_sql - t0, len(rows))

        sources = [{"type": "sql", "table": "products", "rows": len(rows)}]

        if not rows:
            yield {"type": "token", "content": _no_answer_msg(tenant_id)}
            yield {"type": "done", "intent": intent, "sources": []}
            return

        formatted = _format_analytics_answer(intent, rows)
        t_fmt = time.monotonic()
        logger.info("[analytics] format: %.3fs", t_fmt - t_sql)

        if config.ANALYTICS_LLM_INTRO:
            intro = _analytics_intro_sentence(question, len(rows))
            t_llm = time.monotonic()
            logger.info("[analytics] LLM intro: %.3fs", t_llm - t_fmt)
            if intro:
                yield {"type": "token", "content": intro + "\n\n"}

        # Emit the Python-formatted list in small chunks to keep SSE flowing
        _CHUNK = 120
        for i in range(0, len(formatted), _CHUNK):
            yield {"type": "token", "content": formatted[i:i + _CHUNK]}

        yield {"type": "done", "intent": intent, "sources": sources}
        return

    # ── RAG paths ─────────────────────────────────────────────────────────────
    if embed_model is None:
        embed_model = SentenceTransformer(config.EMBED_MODEL)
    if chroma_client is None:
        chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)

    collection_name = config.COLLECTION_PRODUCTS if intent == "product_rag" else config.COLLECTION_DOCS
    try:
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        yield {"type": "token", "content": _no_answer_msg(tenant_id)}
        yield {"type": "done", "intent": intent, "sources": []}
        return

    chunks, _, metadatas, _, _ = retrieve(question, embed_model, collection, tenant_id)
    if not chunks:
        yield {"type": "token", "content": _no_answer_msg(tenant_id)}
        yield {"type": "done", "intent": intent, "sources": []}
        return

    chunks = chunks[: config.MAX_CONTEXT_CHUNKS]
    metadatas = metadatas[: config.MAX_CONTEXT_CHUNKS]
    sources = []
    for m in metadatas:
        entry: dict = {
            "source": m.get("source", "?"),
            "chunk_index": m.get("chunk_index", 0),
        }
        if "product_name" in m:
            entry["product_name"] = m["product_name"]
        if "product_id" in m:
            entry["product_id"] = m["product_id"]
        sources.append(entry)

    prompt = _build_rag_prompt(question, chunks, tenant_id, history)
    for token in ask_ollama_stream(prompt):
        yield {"type": "token", "content": token}
    yield {"type": "done", "intent": intent, "sources": sources}


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
