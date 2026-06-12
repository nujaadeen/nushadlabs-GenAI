"""
tools/analytics.py — Tenant-scoped SQL analytics functions.

All three functions hit PostgreSQL directly — no embeddings, no ChromaDB.
Each is parameterised and returns a list of plain dicts so the router
can pass the data to any downstream formatter without re-querying.
"""

from sqlalchemy import text

from db import get_engine, get_session_factory


def _session():
    return get_session_factory(get_engine())


def _row_to_dict(row) -> dict:
    return {
        "id":           row.id,
        "name":         row.name,
        "price":        float(row.price),
        "discount_pct": float(row.discount_pct),
        "category":     str(row.category),
        "created_at":   row.created_at.isoformat() if row.created_at else None,
        "demand_score": float(row.demand_score),
        "stock":        int(row.stock),
    }


def newest_products(tenant_id: int, limit: int = 5) -> list[dict]:
    """Return the *limit* most recently created products for *tenant_id*."""
    with _session()() as session:
        rows = session.execute(
            text(
                "SELECT id, name, price, discount_pct, category,"
                "       created_at, demand_score, stock"
                "  FROM products"
                " WHERE tenant_id = :tid"
                " ORDER BY created_at DESC"
                " LIMIT :lim"
            ),
            {"tid": tenant_id, "lim": limit},
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def highest_discount_products(tenant_id: int, limit: int = 5) -> list[dict]:
    """Return the *limit* products with the largest discount_pct for *tenant_id*."""
    with _session()() as session:
        rows = session.execute(
            text(
                "SELECT id, name, price, discount_pct, category,"
                "       created_at, demand_score, stock"
                "  FROM products"
                " WHERE tenant_id = :tid"
                " ORDER BY discount_pct DESC"
                " LIMIT :lim"
            ),
            {"tid": tenant_id, "lim": limit},
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def highest_demand_products(tenant_id: int, limit: int = 5) -> list[dict]:
    """Return the *limit* products with the highest demand_score for *tenant_id*."""
    with _session()() as session:
        rows = session.execute(
            text(
                "SELECT id, name, price, discount_pct, category,"
                "       created_at, demand_score, stock"
                "  FROM products"
                " WHERE tenant_id = :tid"
                " ORDER BY demand_score DESC"
                " LIMIT :lim"
            ),
            {"tid": tenant_id, "lim": limit},
        ).fetchall()
    return [_row_to_dict(r) for r in rows]
