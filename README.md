# AMICA

[![Tests](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml)
[![coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Cellular-Semantics/amica/main/.github/badges/coverage.json)](https://github.com/Cellular-Semantics/amica/actions/workflows/test.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

AMICA is a modular agentic pipeline for CxG cell-type annotation, combining publication-driven name expansion and ontology grounding with efficient caching and reproducible experiment workflows.

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Cellular-Semantics/amica.git
cd amica

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create environment and install dependencies
uv sync --dev

# Set up pre-commit hooks (optional but recommended)
uv run pre-commit install

# uv manages dependencies (see [tool.uv] in pyproject.toml)

# Use repo-provided git hooks for consistent checks
git config core.hooksPath .githooks

# Pre-commit hook runs lint, unit tests, and integration tests (requires real API keys)
pre-commit hook runs unit and integration tests before commits.

Generated repo auto-inits git and sets origin to whatever you enter for `git_remote` (default: `git@github.com:Cellular-Semantics/amica.git`). Update the remote if you plan to push elsewhere.
```

### Environment Setup

Create a `.env` file in the project root (never commit secrets). `cellsem_llm_client` automatically loads this file via `python-dotenv`, so once the keys are present you can rely on the client (and the rest of the stack) to access them without extra wiring:

```bash
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

As long as that `.env` file lives at the repo root, `cellsem_llm_client` (and the bootstrapping in `src/amica`) will call `load_dotenv()` and expose those keys to agents, services, and tests automatically—no manual export required.

### Basic Usage

```python
from amica import bootstrap

# Load environment + perform any required startup tasks
bootstrap()
```

### CXG Annotation Workflow

The CXG pipeline expects local input/output folders (defaulting to `resources/cxg`). You can either export `CXG_RESOURCES_DIR=/abs/path/to/resources/cxg` or pass `--resources-dir` to the CLI. A minimal local layout looks like:

```bash
mkdir -p resources/cxg/{input,output,cache,expansions,publications}
# Copy your CXG TSV files into resources/cxg/input
```

Run the workflow with the bundled script:

```bash
scripts/cxg_annotate.py \
  --resources-dir resources/cxg \
  --batch-size 4 \
  --test-mode \
  --test-annotations-count 10
```

Environment overrides:

- `CXG_RESOURCES_DIR`: base directory containing `input`, `output`, `cache`, `expansions`, `publications`
- `CXG_ANNOTATIONS_BATCH_SIZE`: batch size shared by expansion + grounding services
- `CXG_TEST_MODE`: `"1"`/`"true"` to truncate workloads for dry runs
- `CXG_TEST_ANNOTATIONS_COUNT`: number of annotations to keep when test mode is active

The CLI loads these automatically (via `amica.config.load_cxg_configuration()`), so you can mix command-line flags with env vars as needed.

## 📚 Documentation

Documentation lives in `docs/` and is built with Sphinx + MyST. Run `python scripts/check-docs.py` to build with warnings-as-errors before each commit. Publish the rendered HTML via GitHub Pages or your preferred static host.

## ✨ Current Features

- ✅ **Agentic workflow scaffold** with strict TDD guardrails (`CLAUDE.md`)
- ✅ **Unit & integration test suites** pre-configured with pytest markers
- ✅ **Docs + automation scripts** for Sphinx builds
- ✅ **Environment bootstrap** handled via `python-dotenv`
- ✅ **uv-first packaging** (`pyproject.toml` with Ruff, MyPy, pytest config)
- ✅ **Integrated clients**: [`cellsem_llm_client`](https://github.com/Cellular-Semantics/cellsem_llm_client) for LLMs and [`deep-research-client`](https://github.com/monarch-initiative/deep-research-client) for Deepsearch workflows
- ✅ **Pydantic AI graph orchestration**: `pydantic-ai` agent surfaces graph nodes safely with typed deps

## 🏗️ Architecture

```
amica/
├── src/amica/
│   ├── agents/       # Agent classes coordinating workflows
│   ├── graphs/       # Optional workflow graphs powered by Pydantic
│   ├── schemas/      # Shared IO models and contracts
│   └── services/     # LLM + Deepsearch integration layers
├── tests/unit/        # Fast, isolated tests
├── tests/integration/ # Real API + IO validation (no mocks)
├── docs/              # Sphinx configuration and content
└── scripts/           # Tooling helpers (docs, chores, etc.)
```

Optional workflow graphs powered by Pydantic ensure orchestration definitions are validated before agents execute them, keeping schema and runtime behaviors aligned.

- `src/amica/agents`: Agent entrypoints coordinating services and schemas
- `src/amica/graphs`: Optional workflow graphs powered by Pydantic + pydantic-ai
- `src/amica/schemas`: JSON Schema contracts describing outputs + business rules
- `src/amica/services`: Concrete integrations (CellSem LLM client, Deepsearch)
- `src/amica/utils`: Repo-specific tooling/helpers that support workflows without being agents
- `src/amica/validation`: Cross-cutting workflow validations (schema checks, service registration guards)

Workflow validations live in src/amica/validation. Use this module to centralize logic that inspects graphs, schemas, or services before workflows execute.

### Graph Agents with pydantic-ai

```python
from amica.graphs import WorkflowGraph, GraphNode, build_graph_agent, GraphDependencies

graph = WorkflowGraph(
    name="triage",
    entrypoint="collect",
    nodes=[
        GraphNode(id="collect", description="collect context", service="collect_service", next=["summarize"]),
        GraphNode(id="summarize", description="summarize findings", service="summary_service"),
    ],
)

agent = build_graph_agent()
result = agent.run_sync(
    "pick next node",
    deps=GraphDependencies(graph=graph),
    # optional additional instructions/payload
)
```

The `pydantic-ai` agent validates all outputs against `GraphNode`, while dependency injection hands it the validated `WorkflowGraph` for safe routing.

### JSON Schemas for Business Logic

```python
from jsonschema import validate
from amica.schemas import load_schema

schema = load_schema("workflow_output.schema.json")
payload = {
    "status": "completed",
    "summary": "Gathered literature and synthesized insights.",
    "actions": [{"name": "deepsearch.query", "details": "Retrieved 25 documents"}],
}

validate(instance=payload, schema=schema)
```

Schemas stay in JSON so downstream services (Python, JS, workflows) can share the same contract without importing Pydantic models.

### Workflow Validation Helpers

```python
from amica.validation import ensure_services_registered, validate_workflow_output

validate_workflow_output({
    "status": "completed",
    "summary": "Finished triage.",
    "actions": [{"name": "deepsearch.query"}],
})

ensure_services_registered(
    service_names=["deepsearch.query", "summarize"],
    available=["deepsearch.query", "summarize", "collect"],
)
```

Keep complex business logic validations in `src/amica/validation` to centralize enforcement and reuse them across agents and tests.

## 📋 Requirements

- **Python**: 3.11+
- **Dependencies**: Managed via `uv sync --dev`
- **API Keys**: OpenAI + Anthropic keys for integration tests (hard fail if missing)

## 🤝 Contributing

1. Follow the rules in `CLAUDE.md` (TDD-first, tests before code, dotenv usage)
2. Write failing tests, then implement the smallest fix
3. Keep coverage ≥80% and never skip failing tests
4. Run the full quality suite (Ruff, MyPy, pytest, docs) before pushing

### 🧪 Testing Strategy

- **Unit Tests** (`tests/unit`, `@pytest.mark.unit`): no network, deterministic, fast
- **Integration Tests** (`tests/integration`, `@pytest.mark.integration`): real APIs, fail hard if env vars missing
- **Coverage**: target ≥80%, monitored via the coverage badge
- **CI Policy**: GitHub Actions runs only `uv run pytest -m unit`; run `uv run pytest -m integration` locally with real API keys before pushing
- **Hooks**: `.githooks/pre-commit` runs lint, unit tests, and integration tests (skips integration if API keys missing)

### Development Workflow

```bash
# Run tests
uv run pytest                    # All tests
uv run pytest -m unit            # Unit only
uv run pytest -m integration     # Integration only

# Code quality
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run mypy src/

# Docs
python scripts/check-docs.py
```

## 📄 License

MIT License - see `LICENSE` for details.
