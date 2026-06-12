"""
tests/test_isolation.py — Security boundary: tenant 1 must never see tenant 2's chunks.

Strategy:
  - Ingest two distinct corpora under tenants 1 and 2 into a temporary ChromaDB.
  - Cross-query: ask a question whose keywords come from tenant 2's corpus while
    authenticated as tenant 1 (and vice versa).  Because both corpora are semantically
    similar enough that an unfiltered search would surface both, a passing test
    proves the where={"tenant_id": ...} filter is actually enforced.
  - Also verify each tenant still receives its own data.
"""

from unittest.mock import patch

import chromadb
import pytest
from sentence_transformers import SentenceTransformer

import config as rag_config
from ingest import ingest
from query import retrieve

# ---------------------------------------------------------------------------
# Fixture content — repeated enough to produce several chunks each
# ---------------------------------------------------------------------------

_TENANT_1_TEXT = (
    "Alpha Corporation is a leading provider of enterprise software solutions. "
    "Our flagship product AlphaBase powers the data infrastructure of over 500 companies. "
    "AlphaBase features real-time analytics, automated backups, and a 99.99% uptime SLA. "
    "Pricing for AlphaBase starts at $999 per month for the starter tier. "
    "Alpha Corporation was founded in 2010 with offices in New York and London. "
    "Our 200-person engineering team continuously improves AlphaBase performance. "
    "AlphaBase integrates with AWS, Azure, and Google Cloud out of the box. "
    "Enterprise clients receive dedicated support with a four-hour response guarantee. "
) * 5  # ~5 chunks at CHUNK_SIZE=350


_TENANT_2_TEXT = (
    "Beta Dynamics specialises in machine-learning infrastructure for healthcare. "
    "BetaML is our core platform used by hospitals and research institutions worldwide. "
    "BetaML provides HIPAA-compliant data pipelines and federated learning capabilities. "
    "The BetaML platform starts at $1,500 per month and scales with usage. "
    "Beta Dynamics was established in 2015 and is headquartered in San Francisco. "
    "Over 300 healthcare organisations trust BetaML for AI model training. "
    "BetaML complies with FDA 21 CFR Part 11 for regulated medical-device software. "
    "Our 150 ML engineers provide hands-on onboarding and ongoing model-optimisation support. "
) * 5  # ~5 chunks at CHUNK_SIZE=350


# ---------------------------------------------------------------------------
# Module-scoped fixtures so the model and collection are built only once
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def embed_model():
    return SentenceTransformer(rag_config.EMBED_MODEL)


@pytest.fixture(scope="module")
def populated_collection(tmp_path_factory, embed_model):
    chroma_dir = str(tmp_path_factory.mktemp("chroma"))

    def _fake_load_pdf(path: str) -> str:
        return _TENANT_1_TEXT if "t1" in str(path) else _TENANT_2_TEXT

    with (
        patch.object(rag_config, "CHROMA_DIR", chroma_dir),
        patch.object(rag_config, "COLLECTION_NAME", "test_isolation"),
        patch("ingest.load_pdf", side_effect=_fake_load_pdf),
    ):
        ingest(["t1_doc.pdf"], tenant_id=1)
        ingest(["t2_doc.pdf"], tenant_id=2)

    # Return the collection object directly; tests use it without touching config paths
    client = chromadb.PersistentClient(path=chroma_dir)
    return client.get_collection("test_isolation")


# ---------------------------------------------------------------------------
# Isolation tests
# ---------------------------------------------------------------------------

def test_tenant_1_never_sees_tenant_2_chunks(populated_collection, embed_model):
    """
    Query as tenant 1 using keywords that are strongly present in tenant 2's corpus.
    Without the tenant filter, tenant 2 chunks would rank highly.  With it, zero
    tenant 2 chunks must appear.
    """
    _, _, metadatas, _, _ = retrieve(
        "BetaML HIPAA healthcare federated learning",
        embed_model,
        populated_collection,
        tenant_id=1,
        n_results=5,
    )
    for meta in metadatas:
        assert meta["tenant_id"] == 1, (
            f"Tenant 1 query returned a chunk from tenant {meta['tenant_id']} "
            f"(source: {meta.get('source')})"
        )


def test_tenant_2_never_sees_tenant_1_chunks(populated_collection, embed_model):
    """
    Query as tenant 2 using keywords that are strongly present in tenant 1's corpus.
    Without the tenant filter, tenant 1 chunks would rank highly.  With it, zero
    tenant 1 chunks must appear.
    """
    _, _, metadatas, _, _ = retrieve(
        "AlphaBase enterprise analytics uptime SLA pricing",
        embed_model,
        populated_collection,
        tenant_id=2,
        n_results=5,
    )
    for meta in metadatas:
        assert meta["tenant_id"] == 2, (
            f"Tenant 2 query returned a chunk from tenant {meta['tenant_id']} "
            f"(source: {meta.get('source')})"
        )


def test_tenant_1_receives_own_data(populated_collection, embed_model):
    """Tenant 1 must still get results when querying its own corpus."""
    chunks, _, metadatas, _, _ = retrieve(
        "AlphaBase enterprise software",
        embed_model,
        populated_collection,
        tenant_id=1,
        n_results=3,
    )
    assert len(chunks) > 0, "Tenant 1 received no results for its own content"
    for meta in metadatas:
        assert meta["tenant_id"] == 1


def test_tenant_2_receives_own_data(populated_collection, embed_model):
    """Tenant 2 must still get results when querying its own corpus."""
    chunks, _, metadatas, _, _ = retrieve(
        "BetaML healthcare HIPAA compliance",
        embed_model,
        populated_collection,
        tenant_id=2,
        n_results=3,
    )
    assert len(chunks) > 0, "Tenant 2 received no results for its own content"
    for meta in metadatas:
        assert meta["tenant_id"] == 2


def test_chunk_metadata_fields(populated_collection, embed_model):
    """Every stored chunk must carry tenant_id (int), source, and ingest_timestamp."""
    all_items = populated_collection.get(include=["metadatas"])
    for meta in all_items["metadatas"]:
        assert "tenant_id" in meta, f"Missing tenant_id in {meta}"
        assert "source" in meta, f"Missing source in {meta}"
        assert "ingest_timestamp" in meta, f"Missing ingest_timestamp in {meta}"
        assert isinstance(meta["tenant_id"], int), (
            f"tenant_id must be an int, got {type(meta['tenant_id']).__name__}: {meta['tenant_id']!r}"
        )
        assert meta["tenant_id"] in {1, 2}
