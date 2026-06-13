"""
agent.py — Tool-using agent loop.

Replaces the hard intent router with an LLM that decides which tools to call,
may chain multiple calls, and writes a cited final answer.

Entry point:
    agent_stream(question, tenant_id, embed_model, chroma_client, history, limit)
    → Iterator[dict]   (same SSE-compatible dict format as ask_stream)

Tenant isolation:
    tenant_id is injected by _execute_tool at call time; the model is never told
    it and cannot override it.

SSE events emitted:
    {"type": "tool_call",  "tool": "<name>", "args": {...}}
    {"type": "token",      "content": "<text>"}
    {"type": "done",       "intent": "agent", "sources": [...], "tools_called": [...]}
"""

import json
import logging
import time
import urllib.request
from collections.abc import Iterator

import chromadb
from sentence_transformers import SentenceTransformer

import config
from query import retrieve
from tools.analytics import (
    get_product_by_id as _sql_get_product,
    highest_demand_products as _sql_demand,
    highest_discount_products as _sql_discount,
    newest_products as _sql_newest,
)

logger = logging.getLogger(__name__)

_MAX_TURNS = 6  # hard cap on agent iterations before forcing a final answer

# ---------------------------------------------------------------------------
# Tool definitions — Ollama / OpenAI function-calling format
# ---------------------------------------------------------------------------

_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "doc_search",
            "description": (
                "Search company policies, contracts, terms, and documentation "
                "stored as text chunks in the vector database."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Max chunks to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "product_search",
            "description": (
                "Semantic search over product descriptions. Use for open-ended queries "
                "like 'find a laptop' or 'what products do we carry'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "newest_products",
            "description": "Return the most recently added products, sorted by creation date descending.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "highest_discount_products",
            "description": "Return products with the largest percentage discounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "highest_demand_products",
            "description": "Return the most popular / highest-demand products by demand score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_by_id",
            "description": "Fetch full details for a single product using its integer ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Product ID"},
                },
                "required": ["id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_BASE_SYSTEM = (
    "You are a helpful product and document assistant. "
    "Use the available tools to look up information before answering. "
    "Rules:\n"
    "- Call tools to retrieve data; never invent facts not returned by a tool.\n"
    "- If the question can be answered with a SINGLE tool call, make that one call "
    "and answer — do not call more tools than necessary.\n"
    "- You may call more than one tool if the question genuinely requires it.\n"
    "- In your final answer, cite every product by name (and ID if known) and "
    "every document source you relied on.\n"
    "- tenant_id is managed automatically — do not mention it or attempt to set it."
)


def _system_prompt(tenant_id: int) -> str:
    tenant = config.TENANT_REGISTRY.get(tenant_id)
    if tenant:
        intro = f"You are a helpful assistant for {tenant['name']}, {tenant['description']}."
    else:
        intro = "You are a helpful product and document assistant."
    return f"{intro}\n\n{_BASE_SYSTEM}"


# ---------------------------------------------------------------------------
# Ollama /api/chat wrappers
# ---------------------------------------------------------------------------

def _ollama_chat(messages: list[dict], tools: list[dict]) -> dict:
    """Non-streaming POST to /api/chat. Returns the full response dict."""
    url = f"{config.OLLAMA_BASE_URL}/api/chat"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "messages": messages,
        "tools": tools,
        "stream": False,
        "options": {"num_predict": config.LLM_NUM_PREDICT},
        "keep_alive": config.LLM_KEEP_ALIVE,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _ollama_chat_stream(messages: list[dict]) -> Iterator[str]:
    """Streaming POST to /api/chat (no tools). Yields token strings."""
    url = f"{config.OLLAMA_BASE_URL}/api/chat"
    payload = json.dumps({
        "model": config.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"num_predict": config.LLM_NUM_PREDICT},
        "keep_alive": config.LLM_KEEP_ALIVE,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw_line in resp:
            if not raw_line:
                continue
            try:
                data = json.loads(raw_line.decode())
            except json.JSONDecodeError:
                continue
            token = (data.get("message") or {}).get("content", "")
            if token:
                yield token
            if data.get("done"):
                break


# ---------------------------------------------------------------------------
# Tool execution — tenant_id is always injected here, never from the model
# ---------------------------------------------------------------------------

def _execute_tool(
    name: str,
    args: dict,
    tenant_id: int,
    embed_model: SentenceTransformer,
    chroma_client: chromadb.PersistentClient,
    default_limit: int,
) -> str:
    """Run a named tool with tenant-scoped access. Returns a JSON string."""
    limit = int(args.get("limit", default_limit))

    if name == "doc_search":
        try:
            col = chroma_client.get_collection(config.COLLECTION_DOCS)
        except Exception:
            return json.dumps({"error": "Document collection not found"})
        chunks, _, metas, _, _ = retrieve(
            args["query"], embed_model, col, tenant_id, n_results=limit
        )
        return json.dumps({
            "results": [
                {"text": c, "source": m.get("source", "?"), "chunk_index": m.get("chunk_index", 0)}
                for c, m in zip(chunks, metas)
            ]
        })

    if name == "product_search":
        try:
            col = chroma_client.get_collection(config.COLLECTION_PRODUCTS)
        except Exception:
            return json.dumps({"error": "Product collection not found"})
        chunks, _, metas, _, _ = retrieve(
            args["query"], embed_model, col, tenant_id, n_results=limit
        )
        return json.dumps({
            "results": [
                {"text": c, "source": m.get("source", "?"), "chunk_index": m.get("chunk_index", 0)}
                for c, m in zip(chunks, metas)
            ]
        })

    if name == "newest_products":
        return json.dumps({"products": _sql_newest(tenant_id, limit)})

    if name == "highest_discount_products":
        return json.dumps({"products": _sql_discount(tenant_id, limit)})

    if name == "highest_demand_products":
        return json.dumps({"products": _sql_demand(tenant_id, limit)})

    if name == "get_product_by_id":
        product = _sql_get_product(tenant_id, int(args["id"]))
        if product:
            return json.dumps({"product": product})
        return json.dumps({"error": f"Product {args['id']} not found for this tenant"})

    return json.dumps({"error": f"Unknown tool: {name}"})


# ---------------------------------------------------------------------------
# Source / log helpers
# ---------------------------------------------------------------------------

def _extract_sources(tool_name: str, result_str: str) -> list[dict]:
    try:
        r = json.loads(result_str)
    except Exception:
        return []
    if tool_name in ("newest_products", "highest_discount_products", "highest_demand_products"):
        return [{"type": "sql", "table": "products", "rows": len(r.get("products", []))}]
    if tool_name == "get_product_by_id":
        p = r.get("product")
        return [{"type": "sql", "table": "products", "id": p["id"], "name": p["name"]}] if p else []
    if tool_name in ("doc_search", "product_search"):
        return [
            {"source": res.get("source", "?"), "chunk_index": res.get("chunk_index", 0)}
            for res in r.get("results", [])
        ]
    return []


def _result_count(result_str: str) -> str:
    try:
        r = json.loads(result_str)
        for key in ("products", "results"):
            if key in r:
                return str(len(r[key]))
        if "product" in r:
            return "1"
    except Exception:
        pass
    return "?"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def agent_stream(
    question: str,
    tenant_id: int,
    embed_model: SentenceTransformer,
    chroma_client: chromadb.PersistentClient,
    history: list[dict] | None = None,
    limit: int = 5,
) -> Iterator[dict]:
    """
    Run the tool-using agent loop and yield SSE-compatible dicts.

    The model decides which tools to call and may chain multiple calls before
    writing a final cited answer. tenant_id is injected at execution time and
    is never visible to or settable by the model.
    """
    t0 = time.monotonic()
    tools_called: list[dict] = []
    sources: list[dict] = []

    messages: list[dict] = [{"role": "system", "content": _system_prompt(tenant_id)}]
    if history:
        messages.extend(history[-4:])  # last 2 user+assistant pairs
    messages.append({"role": "user", "content": question})

    final_content = ""

    for turn in range(_MAX_TURNS):
        t_llm = time.monotonic()
        try:
            resp = _ollama_chat(messages, _TOOLS)
        except Exception as exc:
            logger.error("[agent] tenant=%d turn=%d LLM error: %s", tenant_id, turn, exc)
            yield {"type": "token", "content": f"[Agent error contacting LLM: {exc}]"}
            break

        llm_ms = (time.monotonic() - t_llm) * 1000
        msg = resp.get("message", {})
        tc_list = msg.get("tool_calls") or []

        logger.info(
            "[agent] tenant=%d turn=%d llm_ms=%.0f tool_calls=%d",
            tenant_id, turn, llm_ms, len(tc_list),
        )

        if not tc_list:
            # Model produced a final answer — no more tool calls needed.
            final_content = (msg.get("content") or "").strip()
            break

        # Append the assistant message (carries tool_calls) to conversation history.
        messages.append(msg)

        for tc in tc_list:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            # Ollama may return arguments as a dict or as a JSON-encoded string.
            raw_args = fn.get("arguments", {})
            args = raw_args if isinstance(raw_args, dict) else json.loads(raw_args or "{}")

            logger.info("[agent] tenant=%d tool_call tool=%s args=%r", tenant_id, name, args)
            yield {"type": "tool_call", "tool": name, "args": args}

            t_tool = time.monotonic()
            result_str = _execute_tool(
                name, args, tenant_id, embed_model, chroma_client, limit
            )
            tool_ms = (time.monotonic() - t_tool) * 1000

            logger.info(
                "[agent] tenant=%d tool_result tool=%s tool_ms=%.0f count=%s",
                tenant_id, name, tool_ms, _result_count(result_str),
            )

            messages.append({"role": "tool", "content": result_str})
            tools_called.append({"tool": name, "args": args})
            sources.extend(_extract_sources(name, result_str))

    # ── Emit final answer ────────────────────────────────────────────────────
    if final_content:
        # Chunk the already-complete response so the SSE contract is consistent.
        _CHUNK = 80
        for i in range(0, len(final_content), _CHUNK):
            yield {"type": "token", "content": final_content[i:i + _CHUNK]}
    else:
        # Hit _MAX_TURNS without a text answer — force a streaming final answer.
        messages.append({
            "role": "user",
            "content": "Based on the tool results above, please give your final answer now.",
        })
        for token in _ollama_chat_stream(messages):
            yield {"type": "token", "content": token}

    total_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "[agent] tenant=%d question=%r tools_called=%s total_ms=%.0f",
        tenant_id, question,
        [t["tool"] for t in tools_called],
        total_ms,
    )

    yield {
        "type": "done",
        "intent": "agent",
        "sources": sources,
        "tools_called": tools_called,
    }
