# Agent UI

A minimal Vite + vanilla JavaScript interface for testing the local RAG agent API.  
No framework, no runtime dependencies — one small codebase a beginner can read.

## Quick start

```bash
cd agent_ui
cp .env.example .env      # edit VITE_PROXY_TARGET if your backend isn't on :8000
npm install
npm run dev               # → http://localhost:5173
```

Open the URL, and the page immediately checks `/health` and shows a green or red
connection indicator. The message box is focused and ready to type.

## What you see

The page has three live panes:

| Pane | What it shows |
|------|---------------|
| **Answer** | Token events reassembled into one growing string. A blinking caret appears while the stream is active. Intent, tools called, and sources appear beneath the text when the server sends `done`. |
| **Tool calls** | One card per `tool_call` SSE event the agent emits, showing the tool name and its arguments. |
| **Raw SSE log** | Every event verbatim, timestamped and colour-coded: amber = token, cyan = tool_call, green = done, red = error. Auto-scrolls while you're at the bottom. |

## Controls

| Control | Description |
|---------|-------------|
| **Bearer token** (top-right) | Sent as `Authorization: Bearer <token>` with every request. Default: `demo-token-tenant-1`. |
| **Enter** | Send the message. |
| **Shift+Enter** | Insert a newline without sending. |
| **New session** | Clears all three panes and resets the session ID, so the next message starts a fresh server-side conversation. |
| **clear** (log header) | Wipes the raw SSE log without affecting the other panes. |

After each request the page shows elapsed seconds and the number of `token` events
received, e.g. `2.3s · 47 token events`.

## Session memory

The server returns a `session_id` in the `done` event.  The UI saves it and
includes it in every subsequent request body so the agent has access to the
conversation history.  The current session ID is displayed below the input box.
Clicking **New session** clears it.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Where the FastAPI backend is running |

Copy `.env.example` to `.env` and change the value if needed.

## Why not EventSource?

`EventSource` is the browser's built-in SSE client, but it only supports `GET`
requests and cannot send custom headers.  This UI needs a `POST` body (for the
message and `session_id`) and an `Authorization: Bearer` header.  Instead we use
`fetch()` + `response.body.getReader()` + `TextDecoder` and parse the SSE frames
manually — buffering partial frames across reads and splitting on `\n\n`.

## Why no CORS errors?

Vite's dev server proxies `/chat` and `/health` to `VITE_PROXY_TARGET`.  The
browser calls relative paths (`/chat`), which are same-origin from the browser's
perspective, so no CORS pre-flight is ever triggered.

## Backend contract

```
POST /chat
  Authorization: Bearer <token>
  Content-Type: application/json
  Body: { "message": "...", "session_id": "..." }   ← omit session_id on first message

  SSE response:
    {"type":"token",     "content":"..."}
    {"type":"tool_call", "tool":"...", "args":{...}}
    {"type":"done",      "intent":"...", "sources":[...],
                         "tools_called":[...], "session_id":"..."}
    {"type":"error",     "message":"..."}

GET /health
  → {"status":"ok", "llm_model":"...", ...}
```
