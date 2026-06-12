"""
app.py — Streamlit RAG Explorer

Sliders for chunk size / overlap / k let you re-index in memory instantly and see
how retrieval quality changes, without touching ChromaDB or config.py.

Run:
    streamlit run app.py

Requires Streamlit:
    pip install streamlit
"""

from pathlib import Path

import numpy as np
import streamlit as st
from sentence_transformers import SentenceTransformer

import config
from ingest import chunk_by_tokens, clean_text, enforce_max_tokens, load_pdf
from query import ask_ollama, build_prompt

# ─── Page setup ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="NovaSpark RAG Explorer", layout="wide")
st.title("NovaSpark RAG Explorer")
st.caption(
    "Experiment with chunking and retrieval settings without touching config.py. "
    "Changing a slider rebuilds the in-memory index automatically."
)

# ─── Sidebar controls ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    model_name = st.selectbox(
        "Embedding model",
        options=[
            "BAAI/bge-small-en-v1.5",
            "sentence-transformers/all-MiniLM-L6-v2",
        ],
        index=0,
        help="Changing the model rebuilds the in-memory index.",
    )

    chunk_size = st.slider(
        "Chunk size (tokens)", min_value=64, max_value=1024,
        value=config.CHUNK_SIZE, step=64,
    )
    max_overlap = max(0, chunk_size - 1)
    overlap = st.slider(
        "Overlap (tokens)", min_value=0, max_value=min(max_overlap, 256),
        value=min(config.CHUNK_OVERLAP, max_overlap), step=10,
    )
    top_k = st.slider("Top-K chunks to retrieve", min_value=1, max_value=15,
                      value=config.TOP_K)
    max_ctx = st.slider(
        "Max context chunks (sent to LLM)", min_value=1, max_value=top_k,
        value=min(config.MAX_CONTEXT_CHUNKS, top_k),
    )

    show_prompt = st.checkbox("Show full prompt", value=False)

    st.divider()
    st.caption(f"LLM: `{config.LLM_MODEL}` via Ollama")


# ─── In-memory index (rebuilt only when settings change) ────────────────────
@st.cache_resource(show_spinner="Building index…")
def build_index(
    model_name: str, chunk_size: int, overlap: int
) -> tuple[SentenceTransformer, list[str], np.ndarray, list[str]]:
    model     = SentenceTransformer(model_name)
    tokenizer = model.tokenizer
    max_tokens = min(510, getattr(model, "max_seq_length", 512) - 2)

    pdf_paths  = sorted(Path(config.DATA_DIR).glob("*.pdf"))
    all_chunks: list[str] = []
    sources:    list[str] = []

    for p in pdf_paths:
        raw    = load_pdf(str(p))
        text   = clean_text(raw)
        chunks = chunk_by_tokens(text, tokenizer, chunk_size, overlap)
        chunks = [clean_text(c) for c in chunks]
        chunks = enforce_max_tokens(chunks, tokenizer, max_tokens)
        all_chunks.extend(chunks)
        sources.extend([p.name] * len(chunks))

    if not all_chunks:
        return model, [], np.empty((0,)), []

    embs = model.encode(all_chunks, normalize_embeddings=True, show_progress_bar=False)
    return model, all_chunks, np.array(embs), sources


model, all_chunks, embeddings, sources = build_index(model_name, chunk_size, overlap)

with st.sidebar:
    st.metric("Indexed chunks", len(all_chunks))


# ─── Question input ──────────────────────────────────────────────────────────
question = st.text_input(
    "Ask a question:",
    placeholder="How many employees does NovaSpark have?",
)

if not question:
    st.info("Type a question above to see retrieved chunks and an LLM answer.")
    st.stop()

if len(all_chunks) == 0:
    st.error(f"No PDFs found in `{config.DATA_DIR}`. Add PDFs and restart.")
    st.stop()

# ─── Retrieval ───────────────────────────────────────────────────────────────
prefix      = config.BGE_QUERY_INSTRUCTION if "bge" in model_name.lower() else ""
q_vec       = model.encode([prefix + question], normalize_embeddings=True)[0]
sims        = embeddings @ q_vec                        # cosine similarity
top_indices = np.argsort(-sims)[: top_k]

col_left, col_right = st.columns([1, 1])

# ─── Left column: retrieved chunks ───────────────────────────────────────────
with col_left:
    st.subheader(f"Retrieved chunks (top {top_k})")
    for rank, idx in enumerate(top_indices):
        sim = float(sims[idx])
        label = f"#{rank+1}  similarity={sim:.4f}  |  {sources[idx]}"
        # Highlight chunks that will actually reach the LLM
        expanded = rank < max_ctx
        with st.expander(label, expanded=expanded):
            if rank < max_ctx:
                st.caption("Included in LLM context")
            else:
                st.caption("Retrieved but NOT sent to LLM (beyond max context)")
            st.text(all_chunks[idx])

# ─── Right column: LLM answer ────────────────────────────────────────────────
with col_right:
    st.subheader("LLM answer")
    context_chunks = [all_chunks[i] for i in top_indices[:max_ctx]]
    prompt = build_prompt(question, context_chunks)

    with st.spinner(f"Asking {config.LLM_MODEL}…"):
        answer, llm_ms = ask_ollama(prompt)

    st.markdown(answer)
    st.caption(
        f"Generated in {llm_ms / 1000:.2f}s  |  "
        f"{len(context_chunks)} of {top_k} chunks in context  |  "
        f"{len(all_chunks)} total chunks indexed"
    )

    if show_prompt:
        st.divider()
        st.subheader("Full prompt")
        st.code(prompt, language="text")
