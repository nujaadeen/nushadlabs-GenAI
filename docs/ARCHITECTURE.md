# Architecture

## Overview

The ERP RAG API is a multi-tenant question-answering service backed by a
**tool-using agent loop**. Instead of a hard-coded intent router, a local
Ollama LLM decides which tools to call, may chain multiple calls, and writes
a cited final answer.

```
User question (HTTP POST /chat)
        │
        ▼
  ┌─────────────┐
  │   api.py    │  — auth, session history, SSE streaming
  └──────┬──────┘
         │  agent_stream(question, tenant_id, ...)
         ▼
  ┌─────────────┐
  │  agent.py   │  — LLM ↔ tool loop (max 6 turns)
  └──────┬──────┘
         │  calls one or more tools
    ┌────┴────────────────────────────┐
    ▼                                 ▼
SQL tools (tools/analytics.py)    Vector tools (ChromaDB via query.retrieve)
newest_products                   doc_search   → COLLECTION_DOCS
highest_discount_products         product_search → COLLECTION_PRODUCTS
highest_demand_products
get_product_by_id
```

---

## Four Capabilities

### 1. Document search (`doc_search`)
Semantic search over company policies, contracts, and documentation ingested
as text chunks into ChromaDB (`COLLECTION_DOCS = "rag_docs"`).  
Use for questions about business rules, terms, or internal procedures.

### 2. Product search (`product_search`)
Semantic search over product descriptions synced into ChromaDB
(`COLLECTION_PRODUCTS = "rag_products"`).  
Use for open-ended discovery: "what products do we carry?", "find a wireless
keyboard".

### 3. Analytics — SQL tools
Three parameterised SQL queries, each returning structured product rows:

| Tool | SQL order | Typical question |
|------|-----------|-----------------|
| `newest_products` | `ORDER BY created_at DESC` | "What are our newest arrivals?" |
| `highest_discount_products` | `ORDER BY discount_pct DESC` | "What's on the biggest sale?" |
| `highest_demand_products` | `ORDER BY demand_score DESC` | "What are our best-sellers?" |

The agent can chain these with other tools, e.g. "Of our newest products,
which is cheapest?" → call `newest_products`, reason over the returned prices.

### 4. Single-product lookup (`get_product_by_id`)
Fetches full details for one product by integer ID.  Used when the agent has
an ID from a previous tool result and needs to confirm or enrich it.

---

## How a Question Flows Through the System

```
1.  POST /chat  {message, session_id?}  + Authorization: Bearer <token>
        │
        │  api.py resolves tenant_id from the token (never from the body).
        │  History for the session (last 6 messages) is prepended to context.
        │
2.  agent_stream() starts the loop
        │
        │  messages = [system_prompt(tenant_id), ...history, user_question]
        │
3.  Turn 0 — non-streaming POST /api/chat to Ollama with tools registered
        │
        │  Ollama returns tool_calls: [{function: {name, arguments}}]
        │
4.  For each tool call:
        │   a. Emit {"type":"tool_call", "tool":"...", "args":{...}}  → SSE
        │   b. _execute_tool() injects tenant_id, runs SQL or ChromaDB query
        │   c. Append {"role":"tool", "content": "<JSON result>"} to messages
        │   d. Log: tenant_id, tool name, latency, row count
        │
5.  Turn 1..N — repeat until Ollama returns content (no tool_calls)
        │
        │  If _MAX_TURNS (6) reached without a text answer, a final streaming
        │  call is made without tools to force an answer.
        │
6.  Final answer is chunked (80 chars/chunk) and emitted as token events.
        │
7.  {"type":"done", "intent":"agent", "sources":[...], "tools_called":[...]}
        │
8.  api.py saves the assistant turn to session history.
```

---

## Tenant Isolation

`tenant_id` is extracted **only** from the validated Bearer token in
`api.py._resolve_tenant()`. It is passed as a Python argument through the
call chain and injected by `_execute_tool()` at query time.

- The model is never told the tenant_id and cannot set it.
- Every SQL query includes `WHERE tenant_id = :tid`.
- Every ChromaDB query includes `where={"tenant_id": tenant_id}`.
- A token for tenant 2 can never retrieve tenant 1's rows, even if the model
  tried to craft a malicious tool argument.

---

## Structured Logging

Every agent turn emits structured log lines (Python `logging`, INFO level):

```
[agent] tenant=1  turn=0  llm_ms=420  tool_calls=1
[agent] tenant=1  tool_call  tool=newest_products  args={'limit': 5}
[agent] tenant=1  tool_result  tool=newest_products  tool_ms=12  count=5
[agent] tenant=1  turn=1  llm_ms=310  tool_calls=0
[agent] tenant=1  question='Of our newest products, which is cheapest?'
        tools_called=['newest_products']  total_ms=745
```

---

## Key Files

| File | Role |
|------|------|
| `api.py` | FastAPI app — auth, session store, SSE endpoint |
| `agent.py` | Tool-using agent loop — LLM + tool dispatch |
| `tools/analytics.py` | SQL analytics functions (tenant-scoped) |
| `query.py` | ChromaDB retrieval helper (`retrieve()`) |
| `config.py` | All tuneable constants (models, paths, flags) |
| `ingest.py` | PDF → ChromaDB ingestion pipeline |
| `sync_products.py` | SQL → ChromaDB product sync |
| `db.py` | SQLAlchemy engine + session factory |
