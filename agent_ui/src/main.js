/**
 * main.js — RAG Agent UI
 *
 * Talks to the local FastAPI backend via Vite's dev-server proxy so that
 * all requests are same-origin and there are no CORS issues.
 *
 * WHY NOT EventSource?
 *   EventSource only supports GET and cannot send the Authorization header.
 *   We use fetch() + response.body.getReader() to stream the SSE response
 *   while also sending a JSON body and a Bearer token.
 *
 * STREAM PARSING:
 *   SSE frames are delimited by double newlines (\n\n).  A single read()
 *   call may deliver multiple frames or a partial frame, so we keep a
 *   running buffer and flush complete frames as they arrive.
 */

// ── DOM references ────────────────────────────────────────────────────────────

const tokenInput    = document.getElementById('token-input');
const msgInput      = document.getElementById('msg-input');
const sendBtn       = document.getElementById('send-btn');
const newSessionBtn = document.getElementById('new-session-btn');
const clearLogBtn   = document.getElementById('clear-log-btn');
const healthEl      = document.getElementById('health');
const healthText    = document.getElementById('health-text');
const statsEl       = document.getElementById('stats');
const sessionDisplay = document.getElementById('session-display');
const answerBody    = document.getElementById('answer-body');
const answerFooter  = document.getElementById('answer-footer');
const toolList      = document.getElementById('tool-list');
const toolCount     = document.getElementById('tool-count');
const logList       = document.getElementById('log-list');

// ── Application state ─────────────────────────────────────────────────────────

// null → first message; server returns a session_id in the "done" event
let sessionId  = null;
let streaming  = false;

// Accumulated answer text for the current request
let answerText    = '';
let tokenEventCnt = 0;

// ── Health check (runs once on page load) ─────────────────────────────────────

async function checkHealth() {
  try {
    const res = await fetch('/health', { signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      const data = await res.json();
      setHealth(true, `backend ready — ${data.llm_model ?? 'unknown model'}`);
    } else {
      setHealth(false, `backend error ${res.status}`);
    }
  } catch {
    setHealth(false, 'backend unreachable — is uvicorn running?');
  }
}

function setHealth(ok, text) {
  healthEl.className = `health ${ok ? 'health-ok' : 'health-err'}`;
  healthText.textContent = text;
}

// ── SSE streaming ─────────────────────────────────────────────────────────────

/**
 * POST /chat and drive the SSE stream until exhausted or errored.
 * Calls handleEvent() for each complete JSON frame.
 */
async function streamChat(message) {
  const token = tokenInput.value.trim() || 'demo-token-tenant-1';

  // Build the request body; omit session_id on the very first message so the
  // server creates a new session and returns a fresh session_id in "done".
  const body = { message };
  if (sessionId) body.session_id = sessionId;

  const response = await fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`);
  }

  const reader  = response.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = '';  // holds bytes that haven't yet formed a complete frame

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    // Append newly received bytes (stream: true keeps the decoder state so
    // multi-byte characters that straddle chunk boundaries are handled).
    buffer += decoder.decode(value, { stream: true });

    // Split on the SSE frame delimiter.  The last element is either empty or
    // an incomplete frame — keep it in the buffer for the next iteration.
    const frames = buffer.split('\n\n');
    buffer = frames.pop(); // always safe: split always yields ≥ 1 element

    for (const frame of frames) {
      // A frame may contain multiple lines (e.g. "event:", "data:", "id:").
      // We only care about "data:" lines.
      for (const line of frame.split('\n')) {
        if (!line.startsWith('data:')) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          handleEvent(JSON.parse(raw));
        } catch {
          logRaw('parse-error', `[parse error] ${raw}`);
        }
      }
    }
  }

  // Flush anything left in the buffer after the stream ends.
  if (buffer.trim()) {
    for (const line of buffer.split('\n')) {
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (!raw) continue;
      try { handleEvent(JSON.parse(raw)); } catch { /* silently drop */ }
    }
  }
}

// ── Event dispatch ────────────────────────────────────────────────────────────

function handleEvent(evt) {
  // Always log every event to the raw pane first.
  logRaw(evt.type ?? 'unknown', evt);

  switch (evt.type) {

    case 'token':
      // Accumulate into one string — never show as separate fragments.
      answerText += evt.content ?? '';
      tokenEventCnt++;
      renderAnswer(/* streaming= */ true);
      break;

    case 'tool_call':
      renderToolCard(evt);
      break;

    case 'done':
      // Persist the server-assigned session_id for the next request.
      if (evt.session_id) {
        sessionId = evt.session_id;
        sessionDisplay.textContent = `session: ${sessionId}`;
      }
      renderAnswer(/* streaming= */ false);
      renderAnswerFooter(evt);
      break;

    case 'error':
      showStreamError(evt.message ?? JSON.stringify(evt));
      break;

    // Unknown types are already logged — nothing else to do.
  }
}

// ── Rendering ─────────────────────────────────────────────────────────────────

/**
 * Write the accumulated answer text into the answer pane.
 * The blinking caret is a CSS ::after pseudo-element on the .streaming class,
 * so prefers-reduced-motion can stop the animation without JS changes.
 */
function renderAnswer(isStreaming) {
  // textContent prevents any XSS from LLM output.
  answerBody.textContent = answerText;
  answerBody.className = `answer-body${isStreaming ? ' streaming' : ''}`;
}

/**
 * Render the intent / tools-called / sources pills after the "done" event.
 * All values are HTML-escaped before insertion.
 */
function renderAnswerFooter(doneEvt) {
  const intent = doneEvt.intent ?? '—';

  // tools_called: [{tool: "name", args: {...}}, ...]
  const tools = (doneEvt.tools_called ?? [])
    .map(t => t.tool ?? t.name ?? '?')
    .join(', ') || '—';

  // sources: shape varies by path — normalise to a display string
  const srcs = (doneEvt.sources ?? [])
    .map(s => s.source ?? s.name ?? s.type ?? JSON.stringify(s))
    .join(', ') || '—';

  answerFooter.innerHTML = `
    <span class="pill pill-intent">${esc(intent)}</span>
    <span class="pill pill-tools">tools: ${esc(tools)}</span>
    <span class="pill pill-sources">sources: ${esc(srcs)}</span>
  `;
}

/**
 * Append one card to the tool-calls pane.
 * Field names from the agent vary — be defensive about all of them.
 */
function renderToolCard(evt) {
  // Try every known field name for the tool name and the arguments.
  const name = evt.name ?? evt.tool ?? evt.tool_name ?? '(unknown)';
  const args = evt.arguments ?? evt.args ?? evt.input;

  const card = document.createElement('div');
  card.className = 'tool-card';

  const argsText = args !== undefined
    ? JSON.stringify(args, null, 2)
    : JSON.stringify(evt, null, 2);  // fallback: pretty-print entire event

  card.innerHTML = `
    <div class="tool-name">${esc(name)}</div>
    <pre class="tool-args">${esc(argsText)}</pre>
  `;

  toolList.appendChild(card);
  toolCount.textContent = toolList.childElementCount;
  toolCount.removeAttribute('hidden');
}

function showStreamError(msg) {
  // Append an error notice without erasing any partial answer.
  const el = document.createElement('div');
  el.className = 'stream-error';
  el.textContent = `Error: ${msg}`;
  answerBody.appendChild(el);
}

// ── Raw SSE log ───────────────────────────────────────────────────────────────

/**
 * Append one timestamped, colour-coded entry to the raw event log.
 * Auto-scrolls only when the user is already at the bottom, so manual
 * scrolling up to read old entries is not interrupted.
 */
function logRaw(type, data) {
  const ts   = new Date().toTimeString().slice(0, 8);
  const body = typeof data === 'string' ? data : JSON.stringify(data);

  const entry = document.createElement('div');
  // CSS colours by type: log-token (amber), log-tool_call (cyan),
  // log-done (green), log-error (red), log-request (blue), etc.
  entry.className = `log-entry log-${CSS.escape(type)}`;
  entry.innerHTML =
    `<span class="log-ts">${esc(ts)}</span>` +
    `<span class="log-body">${esc(body)}</span>`;

  logList.appendChild(entry);

  // Only auto-scroll when the user hasn't scrolled up to read history.
  const nearBottom =
    logList.scrollHeight - logList.scrollTop - logList.clientHeight < 80;
  if (nearBottom) logList.scrollTop = logList.scrollHeight;
}

// ── Controls ──────────────────────────────────────────────────────────────────

/** Clear session state and all three panes; used by "New session" button. */
function clearAll() {
  sessionId     = null;
  answerText    = '';
  tokenEventCnt = 0;

  answerBody.textContent  = '';
  answerBody.className    = 'answer-body';
  answerFooter.innerHTML  = '';
  toolList.innerHTML      = '';
  toolCount.textContent   = '';
  statsEl.textContent     = '';
  sessionDisplay.textContent = '';
}

async function onSend() {
  const msg = msgInput.value.trim();
  if (!msg || streaming) return;

  // Reset the answer pane for the new reply but do NOT clear tools or log —
  // they accumulate across messages in the same session.
  answerText    = '';
  tokenEventCnt = 0;
  answerBody.textContent = '';
  answerBody.className   = 'answer-body streaming';
  answerFooter.innerHTML = '';

  msgInput.value   = '';
  streaming        = true;
  sendBtn.disabled = true;

  const t0 = Date.now();
  logRaw('request', { message: msg, session_id: sessionId });

  try {
    await streamChat(msg);
  } catch (err) {
    showStreamError(String(err));
    logRaw('error', { message: String(err) });
  } finally {
    streaming        = false;
    sendBtn.disabled = false;

    // Remove the blinking caret (streaming class) regardless of how we ended.
    answerBody.classList.remove('streaming');

    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    statsEl.textContent = `${elapsed}s · ${tokenEventCnt} token events`;

    msgInput.focus();
  }
}

// Enter = send; Shift+Enter = newline
msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    onSend();
  }
});

sendBtn.addEventListener('click', onSend);
newSessionBtn.addEventListener('click', () => { clearAll(); msgInput.focus(); });
clearLogBtn.addEventListener('click', () => { logList.innerHTML = ''; });

// ── Utility ───────────────────────────────────────────────────────────────────

/** Minimal HTML escaping — prevents XSS from LLM/API content in innerHTML. */
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Boot ──────────────────────────────────────────────────────────────────────

checkHealth();   // health check fires immediately on page load
msgInput.focus(); // ready to type without clicking
