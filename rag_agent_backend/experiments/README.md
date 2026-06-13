# experiments/

Scratch space for tinkering and evaluation — none of these files are part of
the production package.

| File / folder | Purpose |
|---|---|
| `experiment.py` | Grid search over chunk sizes, overlaps, k values, and embedding models. Prints a comparison table of hit-rate and top-1 similarity. |
| `inspect_embeddings.py` | Teaching tool: prints tokenizer output, embedding dimensions, and cosine similarity for sample sentences. |
| `eval/questions.yaml` | Evaluation question set used by `experiment.py`. |

Run from `rag_agent_backend/` after `pip install -e .`:

```bash
python experiments/experiment.py
python experiments/inspect_embeddings.py
```
