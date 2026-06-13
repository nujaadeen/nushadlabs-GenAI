"""
api.py — FastAPI service wrapping the RAG router for ERP frontend consumption.

Start:
    uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000 --reload

Session memory
--------------
Conversation history is held in a plain Python dict keyed by session_id.
In production replace with Redis:

    import redis.asyncio as redis
    _redis = redis.Redis(host="localhost", decode_responses=True)

    async def _get_history(sid: str) -> list[dict]:
        raw = await _redis.get(f"session:{sid}")
        return json.loads(raw) if raw else []

    async def _set_history(sid: str, history: list[dict]) -> None:
        await _redis.setex(f"session:{sid}", 86400, json.dumps(history))

Bearer token → tenant_id mapping
---------------------------------
For the demo the mapping is a static dict seeded from environment variables.
In production, validate a signed JWT (e.g. PyJWT) and extract the tenant claim:

    import jwt
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return int(payload["tenant_id"])
"""

import asyncio
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

import chromadb
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from rag_agent import config
from rag_agent.retrieval.router import ask_stream

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth: bearer token → tenant_id
# ---------------------------------------------------------------------------

# Override with env vars in production:
#   TENANT_1_TOKEN=<secret1> TENANT_2_TOKEN=<secret2> uvicorn api:app ...
_TOKEN_MAP: dict[str, int] = {
    os.getenv("TENANT_1_TOKEN", "demo-token-tenant-1"): 1,
    os.getenv("TENANT_2_TOKEN", "demo-token-tenant-2"): 2,
    os.getenv("TENANT_3_TOKEN", "demo-token-tenant-3"): 3,
}

_ADMIN_TOKEN: str = os.getenv("ADMIN_TOKEN", "admin-demo-secret")


def _resolve_tenant(authorization: str = Header(...)) -> int:
    """Extract and validate Bearer token; return the mapped tenant_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="Authorization: Bearer <token> required")
    token = authorization.removeprefix("Bearer ").strip()
    tenant_id = _TOKEN_MAP.get(token)
    if tenant_id is None:
        raise HTTPException(403, detail="Unknown or invalid token")
    return tenant_id


def _require_admin(authorization: str = Header(...)) -> None:
    """Guard for admin-only endpoints."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="Authorization: Bearer <token> required")
    token = authorization.removeprefix("Bearer ").strip()
    if token != _ADMIN_TOKEN:
        raise HTTPException(403, detail="Admin access required")


# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

# session_id → list of {"role": "user"|"assistant", "content": str}
_sessions: dict[str, list[dict]] = {}

# Keep the last 3 user+assistant pairs (6 messages) in the prompt window.
# Increase this if you need deeper context; decrease to save tokens.
_MAX_HISTORY_MSGS = 6


def _get_history(session_id: str) -> list[dict]:
    return list(_sessions.get(session_id, []))


def _append_turn(session_id: str, role: str, content: str) -> None:
    history = _sessions.setdefault(session_id, [])
    history.append({"role": role, "content": content})
    if len(history) > _MAX_HISTORY_MSGS:
        _sessions[session_id] = history[-_MAX_HISTORY_MSGS:]


# ---------------------------------------------------------------------------
# Shared resources (loaded once at startup)
# ---------------------------------------------------------------------------

_embed_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _embed_model, _chroma_client
    logger.info("Loading embedding model '%s' …", config.EMBED_MODEL)
    _embed_model = SentenceTransformer(config.EMBED_MODEL)
    _chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    logger.info("Ready — listening for requests.")
    yield
    # nothing to tear down for the demo


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="ERP RAG API", version="0.1.0", description=__doc__, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # lock down to your ERP origin in production
    allow_methods=["POST", "GET"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    # tenant_id in the body is intentionally absent; it is resolved from the
    # Authorization header only so a malicious body cannot escalate tenants.


class IngestRequest(BaseModel):
    tenant_id: int
    pdf_path: Optional[str] = None  # None → ingest all PDFs in config.DATA_DIR


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    """Liveness probe — returns 200 when the service is up and models are loaded."""
    return {
        "status": "ok",
        "embed_model": config.EMBED_MODEL,
        "llm_model": config.LLM_MODEL,
        "ollama_url": config.OLLAMA_BASE_URL,
    }


@app.post("/chat")
async def chat(
    req: ChatRequest,
    tenant_id: int = Depends(_resolve_tenant),
):
    """
    Stream an agent answer for *message* scoped to the authenticated tenant.

    Response is Server-Sent Events (SSE).  Each event is a JSON object:

        {"type": "token",     "content": "<text fragment>"}
        {"type": "tool_call", "tool": "<name>", "args": {...}}   ← optional, for UI
        {"type": "done",      "intent": "agent", "sources": [...],
                              "tools_called": [...], "session_id": "<id>"}
        {"type": "error",     "message": "<description>"}        ← only on failure

    *sources* is a list of cited sources; shape varies by tool:
        SQL tools  → {"type": "sql", "table": "products", "rows": <int>}
        RAG tools  → {"source": "<file>", "chunk_index": <int>}

    *tools_called* lists every tool the agent invoked:
        [{"tool": "<name>", "args": {...}}, ...]
    """
    session_id = req.session_id or str(uuid.uuid4())
    history = _get_history(session_id)
    _append_turn(session_id, "user", req.message)

    # Capture a reference to the shared resources for use in the closure.
    embed_model = _embed_model
    chroma_client = _chroma_client

    async def event_stream() -> AsyncIterator[str]:
        full_answer = ""
        intent = "unknown"
        sources: list[dict] = []
        tools_called: list[dict] = []

        try:
            # ask_stream is a synchronous generator. It handles ROUTER_MODE
            # internally — routing to analytics/RAG or escalating to the agent.
            # Drive it via run_in_executor so the event loop stays free.
            loop = asyncio.get_event_loop()
            sync_gen = ask_stream(
                req.message,
                tenant_id,
                embed_model=embed_model,
                chroma_client=chroma_client,
                history=history,
            )

            def _next():
                try:
                    return next(sync_gen), False
                except StopIteration:
                    return None, True

            while True:
                chunk, exhausted = await loop.run_in_executor(None, _next)
                if exhausted:
                    break
                if chunk["type"] == "token":
                    full_answer += chunk["content"]
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk['content']})}\n\n"
                elif chunk["type"] == "tool_call":
                    # Forward tool-call events so the frontend can optionally
                    # display "thinking…" steps. Unknown event types are safe
                    # to ignore on clients that only handle token/done.
                    yield f"data: {json.dumps(chunk)}\n\n"
                elif chunk["type"] == "done":
                    intent = chunk["intent"]
                    sources = chunk.get("sources", [])
                    tools_called = chunk.get("tools_called", [])

        except Exception as exc:
            logger.exception("Stream error for tenant=%d session=%s", tenant_id, session_id)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

        _append_turn(session_id, "assistant", full_answer)
        yield (
            f"data: {json.dumps({'type': 'done', 'intent': intent, 'sources': sources, 'tools_called': tools_called, 'session_id': session_id})}\n\n"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/ingest")
async def ingest(
    req: IngestRequest,
    _: None = Depends(_require_admin),
):
    """
    Admin-only: trigger PDF ingestion for a tenant.

    Runs ``rag_agent.ingestion.ingest`` as a subprocess so that heavy model
    loading happens out-of-process and does not block the API worker.

    Body:
        tenant_id  — target tenant (integer)
        pdf_path   — optional path to a single PDF; omit to ingest all PDFs
                     in config.DATA_DIR
    """
    from pathlib import Path as _Path
    # cwd = rag_agent_backend/ so that ./data and ./chroma_store resolve correctly
    _backend_dir = str(_Path(__file__).resolve().parents[2])
    cmd = ["python", "-m", "rag_agent.ingestion.ingest", "--tenant-id", str(req.tenant_id)]
    if req.pdf_path:
        cmd += ["--pdf", req.pdf_path]

    logger.info("Admin ingest: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=_backend_dir,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace") if stdout else ""

    if proc.returncode != 0:
        raise HTTPException(500, detail=f"Ingest failed (exit {proc.returncode}):\n{output}")

    return {"status": "ok", "tenant_id": req.tenant_id, "output": output}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rag_agent.api:app", host="0.0.0.0", port=8000, reload=True)
