"""
experiment.py — Grid search over chunk sizes, overlaps, k values, and embedding models.

Evaluates each configuration against eval/questions.yaml and prints a comparison
table showing average top-1 similarity and hit rate (% of questions where a chunk
containing the expected keyword appears in the top-k results).

Usage:
    python experiment.py                          # full grid, default eval file
    python experiment.py --questions eval/questions.yaml
    python experiment.py --models BAAI/bge-small-en-v1.5  # single model
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

import config
from ingest import clean_text, chunk_by_tokens, enforce_max_tokens, load_pdf

# ---------------------------------------------------------------------------
# Grid definition
# ---------------------------------------------------------------------------

CHUNK_SIZES = [256, 512, 1024]
OVERLAPS    = [0, 50, 100]
K_VALUES    = [3, 5, 8]
DEFAULT_MODELS = [
    "BAAI/bge-small-en-v1.5",
    "sentence-transformers/all-MiniLM-L6-v2",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_text(question: str, model_name: str) -> str:
    """Prepend BGE retrieval instruction for BGE models; leave others as-is."""
    if "bge" in model_name.lower():
        return config.BGE_QUERY_INSTRUCTION + question
    return question


def _short_model(name: str) -> str:
    return name.split("/")[-1]


def _dbar(width: int = 80) -> None:
    print("═" * width)


# ---------------------------------------------------------------------------
# Corpus loading (once per run)
# ---------------------------------------------------------------------------

def load_corpus(data_dir: str) -> list[str]:
    """Return concatenated raw text from all PDFs in data_dir."""
    pdf_paths = sorted(Path(data_dir).glob("*.pdf"))
    if not pdf_paths:
        print(f"[experiment] ERROR: No PDFs found in '{data_dir}'.")
        sys.exit(1)
    texts = []
    for p in pdf_paths:
        raw = load_pdf(str(p))
        texts.append(clean_text(raw))
    print(f"[experiment] Loaded {len(pdf_paths)} PDF(s), "
          f"{sum(len(t) for t in texts):,} chars total.")
    return texts


# ---------------------------------------------------------------------------
# Single configuration evaluation
# ---------------------------------------------------------------------------

def evaluate_config(
    clean_texts: list[str],
    questions: list[dict],
    model: SentenceTransformer,
    model_name: str,
    chunk_size: int,
    overlap: int,
    k_values: list[int],
) -> list[dict]:
    """
    Chunk + embed corpus, embed questions, compute similarities, return a row
    dict for every (chunk_size, overlap, k) combination.
    """
    tokenizer  = model.tokenizer
    max_tokens = min(510, getattr(model, "max_seq_length", 512) - 2)

    # Build chunk list
    all_chunks: list[str] = []
    for text in clean_texts:
        chunks = chunk_by_tokens(text, tokenizer, chunk_size, overlap)
        chunks = [clean_text(c) for c in chunks]
        chunks = enforce_max_tokens(chunks, tokenizer, max_tokens)
        all_chunks.extend(chunks)

    n_chunks = len(all_chunks)
    if n_chunks == 0:
        return []

    # Embed chunks (document side — no instruction prefix)
    chunk_embs = model.encode(all_chunks, normalize_embeddings=True, show_progress_bar=False)
    chunk_embs = np.array(chunk_embs)           # (n_chunks, dim)

    # Embed questions (query side — BGE prefix when applicable)
    q_texts = [_query_text(q["question"], model_name) for q in questions]
    q_embs  = model.encode(q_texts, normalize_embeddings=True, show_progress_bar=False)
    q_embs  = np.array(q_embs)                  # (n_q, dim)

    # Cosine similarities (both sides are L2-normalised → plain dot product)
    sims = q_embs @ chunk_embs.T                # (n_q, n_chunks)

    avg_top1_sim = float(sims.max(axis=1).mean())

    rows = []
    for k in k_values:
        actual_k = min(k, n_chunks)
        top_k_idx = np.argsort(-sims, axis=1)[:, :actual_k]   # (n_q, actual_k)

        hits = 0
        for q_idx, q in enumerate(questions):
            keyword = q["keyword"].lower()
            top_chunks = [all_chunks[i] for i in top_k_idx[q_idx]]
            if any(keyword in c.lower() for c in top_chunks):
                hits += 1

        rows.append({
            "model":        _short_model(model_name),
            "chunk_size":   chunk_size,
            "overlap":      overlap,
            "k":            k,
            "n_chunks":     n_chunks,
            "avg_top1_sim": avg_top1_sim,
            "hit_rate":     hits / len(questions),
            "hits":         hits,
            "n_questions":  len(questions),
        })
    return rows


# ---------------------------------------------------------------------------
# Results table printing
# ---------------------------------------------------------------------------

_COL = {
    "rank":        4,
    "model":       22,
    "chunk_size":  7,
    "overlap":     6,
    "k":           4,
    "n_chunks":    7,
    "top1_sim":    10,
    "hit_rate":    10,
}


def _header_line() -> str:
    return (
        f" {'#':>{_COL['rank']}} │"
        f" {'Model':<{_COL['model']}} │"
        f" {'ChkSz':>{_COL['chunk_size']}} │"
        f" {'Ovlp':>{_COL['overlap']}} │"
        f" {'K':>{_COL['k']}} │"
        f" {'Chunks':>{_COL['n_chunks']}} │"
        f" {'Top-1 Sim':>{_COL['top1_sim']}} │"
        f" {'Hit Rate':>{_COL['hit_rate']}}"
    )


def _row_line(rank: int, row: dict, star: bool = False) -> str:
    suffix = "  ★ BEST" if star else ""
    return (
        f" {rank:>{_COL['rank']}} │"
        f" {row['model']:<{_COL['model']}} │"
        f" {row['chunk_size']:>{_COL['chunk_size']}} │"
        f" {row['overlap']:>{_COL['overlap']}} │"
        f" {row['k']:>{_COL['k']}} │"
        f" {row['n_chunks']:>{_COL['n_chunks']}} │"
        f" {row['avg_top1_sim']:>{_COL['top1_sim']}.4f} │"
        f" {row['hit_rate']:>{_COL['hit_rate']}.1%}"
        f"{suffix}"
    )


def _sep_line() -> str:
    return (
        f" {'─'*_COL['rank']}─┼"
        f"─{'─'*_COL['model']}─┼"
        f"─{'─'*_COL['chunk_size']}─┼"
        f"─{'─'*_COL['overlap']}─┼"
        f"─{'─'*_COL['k']}─┼"
        f"─{'─'*_COL['n_chunks']}─┼"
        f"─{'─'*_COL['top1_sim']}─┼"
        f"─{'─'*_COL['hit_rate']}─"
    )


def print_results(all_rows: list[dict], n_questions: int) -> None:
    # Sort: hit_rate DESC, avg_top1_sim DESC, k ASC
    sorted_rows = sorted(
        all_rows,
        key=lambda r: (-r["hit_rate"], -r["avg_top1_sim"], r["k"]),
    )

    width = len(_header_line())
    _dbar(width)
    print(f" RESULTS TABLE  ({n_questions} eval questions — sorted by Hit Rate ↓ then Similarity ↓)")
    _dbar(width)
    print(_header_line())
    print(_sep_line())
    for i, row in enumerate(sorted_rows):
        star = (i == 0)
        print(_row_line(i + 1, row, star=star))
    _dbar(width)

    # Per-model summary
    models = list(dict.fromkeys(r["model"] for r in sorted_rows))
    print("\n Per-model best hit rate:")
    for m in models:
        model_rows = [r for r in sorted_rows if r["model"] == m]
        best = model_rows[0]  # already sorted
        avg_hr = sum(r["hit_rate"] for r in model_rows) / len(model_rows)
        print(f"   {m:<25}  best={best['hit_rate']:.1%}  "
              f"(chunk_size={best['chunk_size']}, overlap={best['overlap']}, k={best['k']})  "
              f"avg across all configs={avg_hr:.1%}")

    # Winner
    winner = sorted_rows[0]
    print()
    _dbar(width)
    print(
        f" WINNER: {winner['model']}  │  "
        f"chunk_size={winner['chunk_size']}  │  "
        f"overlap={winner['overlap']}  │  "
        f"k={winner['k']}  │  "
        f"hit_rate={winner['hit_rate']:.1%}  │  "
        f"top-1 sim={winner['avg_top1_sim']:.4f}"
    )
    if len(models) > 1:
        for m in models:
            avg_hr = sum(r["hit_rate"] for r in sorted_rows if r["model"] == m) / len(sorted_rows) * len(models)
            print(f"   {m}: avg hit rate = {avg_hr:.1%}")
    _dbar(width)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grid-search chunking/retrieval settings against an eval set",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--questions", default="eval/questions.yaml", metavar="FILE",
        help="YAML file with question + keyword pairs",
    )
    parser.add_argument(
        "--models", nargs="+", default=DEFAULT_MODELS, metavar="MODEL",
        help="Sentence-transformers model IDs to compare",
    )
    parser.add_argument(
        "--chunk-sizes", nargs="+", type=int, default=CHUNK_SIZES, metavar="N",
        help="Token chunk sizes to sweep",
    )
    parser.add_argument(
        "--overlaps", nargs="+", type=int, default=OVERLAPS, metavar="N",
        help="Overlap token counts to sweep",
    )
    parser.add_argument(
        "--k-values", nargs="+", type=int, default=K_VALUES, metavar="K",
        help="Top-k values to evaluate",
    )
    args = parser.parse_args()

    # ── Load eval questions ──────────────────────────────────────────────────
    q_path = Path(args.questions)
    if not q_path.exists():
        print(f"[experiment] ERROR: eval file not found: '{q_path}'")
        sys.exit(1)
    with open(q_path) as f:
        eval_data = yaml.safe_load(f)
    questions: list[dict] = eval_data["questions"]
    print(f"[experiment] Loaded {len(questions)} eval questions from '{q_path}'.")

    # ── Load corpus ──────────────────────────────────────────────────────────
    clean_texts = load_corpus(config.DATA_DIR)

    # ── Grid search ─────────────────────────────────────────────────────────
    valid_combos = [
        (cs, ov) for cs in args.chunk_sizes for ov in args.overlaps if ov < cs
    ]
    total = len(args.models) * len(valid_combos)
    print(f"\n[experiment] Grid: {len(args.models)} model(s) × "
          f"{len(valid_combos)} chunk configs = {total} configurations "
          f"× {len(args.k_values)} k values = {total * len(args.k_values)} rows.\n")

    all_rows: list[dict] = []
    wall_start = time.perf_counter()

    for m_idx, model_name in enumerate(args.models):
        print(f"[{m_idx+1}/{len(args.models)}] Loading model: {model_name} …")
        model = SentenceTransformer(model_name)

        for cs, ov in valid_combos:
            t0 = time.perf_counter()
            rows = evaluate_config(
                clean_texts, questions, model, model_name,
                chunk_size=cs, overlap=ov, k_values=args.k_values,
            )
            elapsed = time.perf_counter() - t0
            if rows:
                n_chunks = rows[0]["n_chunks"]
                hit_summary = "  ".join(
                    f"hit@{r['k']}={r['hit_rate']:.0%}" for r in rows
                )
                print(f"   chunk_size={cs:>4}, overlap={ov:>3} "
                      f"→ {n_chunks:>3} chunks  {hit_summary}  ({elapsed:.1f}s)")
                all_rows.extend(rows)
        print()

    total_elapsed = time.perf_counter() - wall_start
    print(f"[experiment] Finished in {total_elapsed:.1f}s.\n")

    if not all_rows:
        print("[experiment] No results to display.")
        sys.exit(0)

    print_results(all_rows, n_questions=len(questions))


if __name__ == "__main__":
    main()
