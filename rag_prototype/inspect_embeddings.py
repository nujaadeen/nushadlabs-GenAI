"""
inspect_embeddings.py — Teaching tool: look inside the tokenizer and embedding space.

Prints:
  1. Tokenizer output for a sample sentence (tokens, IDs, count)
  2. Embedding dimension and first 10 values
  3. Cosine similarity between two example sentences

Usage:
    python inspect_embeddings.py
"""

import math
import config
from sentence_transformers import SentenceTransformer


# ---------------------------------------------------------------------------
# Sentences to inspect (edit these freely)
# ---------------------------------------------------------------------------

SENTENCE_A = "Our company provides cloud-based data analytics solutions."
SENTENCE_B = "We sell software for business intelligence and data analysis."
SENTENCE_C = "I enjoy hiking in the mountains on weekends."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _hr(title: str = "", width: int = 70) -> None:
    if title:
        pad = (width - len(title) - 2) // 2
        print("─" * pad + f" {title} " + "─" * pad)
    else:
        print("─" * width)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\nLoading model '{config.EMBED_MODEL}' …\n")
    model = SentenceTransformer(config.EMBED_MODEL)
    tokenizer = model.tokenizer

    # ── 1. Tokenizer deep-dive ────────────────────────────────────────────
    _hr("1. TOKENIZER OUTPUT")
    print(f"Input sentence:\n  \"{SENTENCE_A}\"\n")

    encoding = tokenizer(SENTENCE_A, add_special_tokens=True)
    token_ids = encoding["input_ids"]

    # Decode each ID individually to show the token string
    tokens = [tokenizer.convert_ids_to_tokens([tid])[0] for tid in token_ids]

    print(f"{'Index':<6} {'Token ID':<12} {'Token string'}")
    print("─" * 40)
    for i, (tok, tid) in enumerate(zip(tokens, token_ids)):
        print(f"{i:<6} {tid:<12} {tok}")

    print(f"\nTotal token count (incl. special tokens): {len(token_ids)}")
    print(f"  → without special tokens: "
          f"{len(tokenizer.encode(SENTENCE_A, add_special_tokens=False))}")

    # ── 2. Embedding vector ───────────────────────────────────────────────
    _hr("2. EMBEDDING VECTOR")
    embedding = model.encode(SENTENCE_A, normalize_embeddings=True)
    dim = len(embedding)
    preview = embedding[:10].tolist()

    print(f"Model: {config.EMBED_MODEL}")
    print(f"Vector dimension: {dim}")
    print(f"\nFirst 10 values (out of {dim}):")
    for i, val in enumerate(preview):
        bar = "█" * int(abs(val) * 20)
        sign = "+" if val >= 0 else "-"
        print(f"  [{i:>3}]  {sign}{abs(val):.6f}  {bar}")
    print(f"\n  (Each dimension captures a different semantic feature.)")
    print(f"  (Normalized vectors live on the unit sphere — ||v|| = "
          f"{sum(x**2 for x in embedding)**0.5:.6f})")

    # ── 3. Cosine similarity ──────────────────────────────────────────────
    _hr("3. COSINE SIMILARITY")
    print("Cosine similarity ranges from -1 (opposite) to +1 (identical).\n")

    pairs = [
        (SENTENCE_A, SENTENCE_B, "Related sentences (both about data/analytics)"),
        (SENTENCE_A, SENTENCE_C, "Unrelated sentences (analytics vs hiking)"),
        (SENTENCE_A, SENTENCE_A, "Identical sentences (sanity check → should be 1.0)"),
    ]

    embs = model.encode(
        [SENTENCE_A, SENTENCE_B, SENTENCE_C],
        normalize_embeddings=True,
    )
    sent_map = {SENTENCE_A: embs[0], SENTENCE_B: embs[1], SENTENCE_C: embs[2]}

    for s1, s2, label in pairs:
        sim = cosine_similarity(sent_map[s1].tolist(), sent_map[s2].tolist())
        bar_len = max(0, int((sim + 1) / 2 * 30))   # scale [-1,1] → [0,30]
        bar = "█" * bar_len
        print(f"  {label}")
        print(f"    A: \"{s1[:60]}\"")
        print(f"    B: \"{s2[:60]}\"")
        print(f"    Similarity: {sim:+.4f}  |{bar:<30}|")
        print()

    _hr()
    print("Tip: ChromaDB stores cosine DISTANCE = 1 - similarity.")
    print("     So a distance of 0.05 means similarity ≈ 0.95 (very close).")
    print("     In query.py output, look for low distances = good matches.\n")


if __name__ == "__main__":
    main()
