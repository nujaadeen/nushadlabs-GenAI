import sys
from pathlib import Path

# Make rag_prototype/ importable (ingest, query, config) from the tests sub-directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
