# AMICA – CXG Annotation Pipeline

[![Tests](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Cellular-Semantics/amica/main/.github/badges/coverage.json)](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

AMICA is a production-ready workflow that expands and grounds CXG cell-type annotations. It ingests CXG TSV exports, enriches labels using curated publication text, and resolves each annotation to the Cell Ontology with full caching and reproducible outputs.

---

## 1. Prerequisites

- **Python** 3.11+
- **uv** for dependency management: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `.env` at repo root with at least:

  ```bash
  OPENAI_API_KEY=sk-...
  ANTHROPIC_API_KEY=sk-ant-...
  ```

- CXG dataset TSVs placed under a workspace directory (default `resources/cxg/input`).

---

## 2. Install & Bootstrap

```bash
git clone https://github.com/Cellular-Semantics/amica.git
cd amica
uv sync --dev
uv run pre-commit install          # optional but recommended
git config core.hooksPath .githooks
```

AMICA auto-loads `.env` during `amica.bootstrap()`, so agents and CLI scripts can access API keys immediately.

---

## 3. Preparing CXG Resources

```
resources/
└── cxg/
    ├── input/          # CXG TSVs (one per dataset)
    ├── publications/   # cached publication text (auto-written)
    ├── expansions/     # paper-cell expansion cache
    ├── cache/          # annotator grounding cache
    └── output/         # generated TSV reports per dataset
```

Create the structure (or point `CXG_RESOURCES_DIR` elsewhere):

```bash
mkdir -p resources/cxg/{input,output,cache,expansions,publications}
export CXG_RESOURCES_DIR=$PWD/resources/cxg
```

Drop your CXG TSVs (columns: `author_cell_type`, `CL_ID`, `CL_label`, `reference`, etc.) into `input/`.

---

## 4. Running the Workflow

```bash
scripts/cxg_annotate.py \
  --resources-dir resources/cxg \
  --batch-size 4 \
  --test-mode \
  --test-annotations-count 25
```

Key flags / env vars:

| Flag / Env                       | Description                                                       |
|---------------------------------|-------------------------------------------------------------------|
| `--resources-dir` / `CXG_RESOURCES_DIR` | Base directory containing `input`, `output`, caches.            |
| `--batch-size` / `CXG_ANNOTATIONS_BATCH_SIZE` | Batch size used by expansion + grounding agents.               |
| `--test-mode` / `CXG_TEST_MODE` | Enable truncated runs for smoke tests.                            |
| `--test-annotations-count` / `CXG_TEST_ANNOTATIONS_COUNT` | Number of annotations preserved when test mode is active. |

The CLI performs three orchestrated stages:

1. **prepare_data** – loads TSVs, normalises rows, downloads publication text.
2. **expand_full_names** – batches annotations per article and uses the Paper CellType agent to enrich labels (`full_name`, synonyms, tissue context).
3. **ground_annotations** – calls the annotator agent with enrichment JSON to resolve CL IDs and writes per-dataset reports:
   - `cell_type_annotations_un_filtered.tsv`
   - `groundings.tsv` (only rows with grounded CL IDs + correctness flag).

All intermediate results are cached so reruns skip unchanged work.

---

## 5. Architecture Snapshot

```
src/amica/
├── agents/annotator/          # Annotator agent + tools (CL search)
├── agents/paper_celltype/     # Paper-aware expansion agent
├── services/                  # Dataset loader, publication fetcher, expansion + grounding services
├── graphs/cxg_annotate.py     # Workflow graph + orchestration helpers
├── utils/cxg.py               # Shared config/models for CXG state
└── config.py                  # Loader for env-driven CXG settings
```

- **Services** operate only on CXG concerns (TSV ingestion, caching, LLM calls).
- **Graph** defines the linear flow (`prepare_data → expand_full_names → ground_annotations`) for reproducibility and tooling.
- **CLI** wires env config + services, providing a single command to process entire CXG drops.

---

## 6. Testing

```bash
uv run pytest -m unit           # includes tests/unit/test_cxg_workflow.py (dummy services)
uv run pytest -m integration    # requires live API keys + data (optional)
```

The unit test suite stubs out agents/services to ensure the workflow graph executes correctly without touching external systems. Add integration tests that point to small fixtures if you need end-to-end verification.

---

## 7. Maintenance Notes

- All workflow settings live in `amica.utils.cxg.CxgPipelineSettings` / `CxgResourceLayout`; prefer env vars over hard-coded paths.
- Cached data (`cache/`, `expansions/`, `publications/`, `output/`) is ignored via `.gitignore`. Clean these directories if you need a fresh run.
- Legacy script (`scripts/archive/cxg_annotate_graph.py`) is preserved only for reference; always use `scripts/cxg_annotate.py`.

---

## License

MIT — see `LICENSE`.
