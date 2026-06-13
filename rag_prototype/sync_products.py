"""
sync_products.py — Sync ERP product rows into a ChromaDB "products" collection.

Each product is embedded as:
    "{name}. {description}. Category: {category}."

Rich metadata (tenant_id, product_id, price, discount_pct, category,
created_at, demand_score, stock) is stored alongside the vector so callers
can filter and sort without reading back the full row.

Incremental sync:
    On each run the script reads product_sync_state.json (created next to
    this file).  For every tenant it stores the highest updated_at seen so
    far, and only rows whose GREATEST(created_at, updated_at) exceeds that
    watermark are re-embedded.  A --full flag bypasses the watermark.

Usage:
    python sync_products.py                    # all tenants, incremental
    python sync_products.py --tenant-id 2      # one tenant, incremental
    python sync_products.py --full             # all tenants, full re-embed
    python sync_products.py --query "cheap waterproof item" --tenant-id 2
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer
from sqlalchemy import func

import config
from db import Product, get_session_factory

# ── Constants ────────────────────────────────────────────────────────────────

SYNC_STATE_PATH = Path(__file__).with_name("product_sync_state.json")

# Epoch used as the "never synced before" watermark
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ── Sync-state helpers ───────────────────────────────────────────────────────

def _load_state() -> dict[str, str]:
    if SYNC_STATE_PATH.exists():
        return json.loads(SYNC_STATE_PATH.read_text())
    return {}


def _save_state(state: dict[str, str]) -> None:
    SYNC_STATE_PATH.write_text(json.dumps(state, indent=2))


def _watermark(state: dict[str, str], tenant_id: int) -> datetime:
    ts = state.get(str(tenant_id))
    if ts:
        return datetime.fromisoformat(ts)
    return _EPOCH


def _update_watermark(state: dict[str, str], tenant_id: int, rows: list) -> None:
    """Advance the watermark to the highest updated_at seen in this batch."""
    if not rows:
        return
    latest = max(
        max(r.created_at, r.updated_at)
        for r in rows
    )
    current = _watermark(state, tenant_id)
    if latest > current:
        state[str(tenant_id)] = latest.isoformat()


# ── Text representation ──────────────────────────────────────────────────────

def _product_text(p: Product) -> str:
    return f"{p.name}. {p.description}. Category: {p.category}."


# ── ChromaDB helpers ─────────────────────────────────────────────────────────

def _chroma_id(p: Product) -> str:
    return f"t{p.tenant_id}_p{p.id}"


def _chroma_metadata(p: Product) -> dict:
    return {
        "tenant_id":    int(p.tenant_id),
        "product_id":   int(p.id),
        "product_name": str(p.name),
        "source":       "products_db",
        "chunk_index":  0,
        "price":        float(p.price),
        "discount_pct": float(p.discount_pct),
        "category":     str(p.category),
        "created_at":   p.created_at.isoformat(),
        "demand_score": float(p.demand_score),
        "stock":        int(p.stock),
    }


# ── Core sync logic ───────────────────────────────────────────────────────────

def sync_tenant(
    tenant_id: int,
    session_factory,
    collection,
    model: SentenceTransformer,
    state: dict[str, str],
    full: bool = False,
) -> int:
    watermark = _EPOCH if full else _watermark(state, tenant_id)

    with session_factory() as session:
        # Use GREATEST(created_at, updated_at) so both new rows and in-place
        # updates (price, stock, discount changes) are captured.
        rows = (
            session.query(Product)
            .filter(
                Product.tenant_id == tenant_id,
                func.greatest(Product.created_at, Product.updated_at) > watermark,
            )
            .order_by(func.greatest(Product.created_at, Product.updated_at))
            .all()
        )

    if not rows:
        print(f"[sync] tenant={tenant_id}  no rows changed since {watermark.isoformat()}")
        return 0

    print(f"[sync] tenant={tenant_id}  embedding {len(rows)} product(s) …")
    texts = [_product_text(p) for p in rows]

    t0 = time.perf_counter()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    embed_ms = (time.perf_counter() - t0) * 1000

    ids       = [_chroma_id(p) for p in rows]
    metadatas = [_chroma_metadata(p) for p in rows]

    collection.upsert(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )

    _update_watermark(state, tenant_id, rows)
    print(f"[sync] tenant={tenant_id}  upserted {len(rows)} vector(s)  "
          f"(embed: {embed_ms:.0f} ms)")
    return len(rows)


def sync_all(tenant_ids: list[int], full: bool = False) -> None:
    print(f"[sync] Loading embedding model '{config.EMBED_MODEL}' …")
    model = SentenceTransformer(config.EMBED_MODEL)

    chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    collection = chroma_client.get_or_create_collection(
        name=config.COLLECTION_PRODUCTS,
        metadata={"hnsw:space": "cosine"},
    )

    session_factory = get_session_factory()
    state = {} if full else _load_state()
    total = 0

    for tid in tenant_ids:
        total += sync_tenant(tid, session_factory, collection, model, state, full=full)

    _save_state(state)
    print(f"\n[sync] Done.  {total} product(s) upserted into "
          f"collection '{config.COLLECTION_PRODUCTS}'  "
          f"(total vectors: {collection.count()})")


# ── Demo search ──────────────────────────────────────────────────────────────

def search_products(query: str, tenant_id: int, n_results: int = 5) -> None:
    print(f"\n[search] query='{query}'  tenant={tenant_id}  top_k={n_results}")

    model = SentenceTransformer(config.EMBED_MODEL)
    prefix = config.BGE_QUERY_INSTRUCTION if "bge" in config.EMBED_MODEL.lower() else ""
    q_vec = model.encode([prefix + query], normalize_embeddings=True)

    chroma_client = chromadb.PersistentClient(path=config.CHROMA_DIR)
    try:
        collection = chroma_client.get_collection(config.COLLECTION_PRODUCTS)
    except Exception:
        print(f"[search] ERROR: collection '{config.COLLECTION_PRODUCTS}' not found. "
              "Run sync_products.py first.")
        sys.exit(1)

    results = collection.query(
        query_embeddings=q_vec.tolist(),
        n_results=n_results,
        where={"tenant_id": tenant_id},
        include=["documents", "distances", "metadatas"],
    )

    docs      = results["documents"][0]
    distances = results["distances"][0]
    metas     = results["metadatas"][0]

    if not docs:
        print("[search] No results found.")
        return

    print(f"{'─' * 80}")
    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metas), 1):
        similarity = 1.0 - dist
        price     = meta["price"]
        discount  = meta["discount_pct"]
        effective = price * (1 - discount / 100)
        print(
            f"\n[{i}]  similarity={similarity:.4f}  "
            f"price=${price:.2f}"
            + (f"  -{discount:.0f}% → ${effective:.2f}" if discount else "")
            + f"  stock={meta['stock']}  demand={meta['demand_score']}  "
            f"category={meta['category']}"
        )
        print(f"     {doc}")
    print(f"{'─' * 80}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync ERP products into ChromaDB and optionally search them.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tenant-id", type=int, default=None, metavar="N",
        help="Sync / search a single tenant.  Omit to process all tenants in TENANT_REGISTRY.",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Ignore last_synced_at and re-embed all rows (full rebuild).",
    )
    parser.add_argument(
        "--query", default=None, metavar="TEXT",
        help="After syncing, run a semantic search and print results.",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, metavar="N",
        help="Number of results to return for --query.",
    )
    args = parser.parse_args()

    tenant_ids = (
        [args.tenant_id]
        if args.tenant_id is not None
        else list(config.TENANT_REGISTRY.keys())
    )

    sync_all(tenant_ids, full=args.full)

    if args.query:
        tid = args.tenant_id
        if tid is None:
            print("[search] --query requires --tenant-id; defaulting to first tenant.")
            tid = tenant_ids[0]
        search_products(args.query, tenant_id=tid, n_results=args.top_k)


if __name__ == "__main__":
    main()
