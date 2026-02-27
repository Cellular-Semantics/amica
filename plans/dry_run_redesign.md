# Dry-Run Output Redesign

## Problem

Current `--dry-run` output dumps raw implementation artifacts: verbose Pydantic
JSON schemas (~200 lines), full prompts verbatim, and redundant derived paths.
It is hard to read and communicates implementation rather than intent.

## Goal

Reorganise output around graph steps and the functional spec. Each step block
should say: what it does, what goes in, what comes out, the agent/prompt in
summary, and the schema as a compact field table.

## New Output Format

```text
=== Pipeline: cxg_annotate ===
Aim: Map cell type annotation names to CL terms by extracting full names and
     synonyms from source publications.

── prepare_data ─────────────────────────────────────────────────
Load TSV inputs and fetch publication text for each DOI.
  Input  : {input_dir}/*.tsv  (annotation_text, DOI, cl_id, cl_label)
  Output : AnnotationRecord list grouped by article

── expand_full_names  [paper_celltype / gpt-5] ──────────────────
Query paper text to resolve each annotation name to its full form.
  Input  : annotation name list + article text  [{cc_json}, {article_context}]
  Output : name → full_name, paper_synonyms, tissue_context

  System Prompt (paper_celltype_agent.py, 8 lines):
    You are a Biocuration Assistant. Extract precise cell type information from
    academic paper content. No external knowledge; no hallucination.

  User Prompt Template  →  references/expansion-prompt.md

  Output Schema:
    name            str       Exact cc.label from input JSON
    full_name       str|None  Expanded full name as defined in paper
    paper_synonyms  str|None  Synonyms from paper, semicolon-separated
    tissue_context  str|None  Quoted tissue/anatomical terms from paper

── ground_annotations  [annotator / gpt-5] ──────────────────────
Map full names and synonyms to CL via OAK (search_cl).
  Input  : CellTypeEntry list  (batch_size=4)
  Output : annotation → cl_id, cl_label

  System Prompt (annotator_agent.py, 45 lines):
    Map text spans to Cell Ontology terms. Prioritise CL over UBERON;
    prefer broader canonical terms for generic inputs; penalise over-specific
    qualifiers. [full prompt: annotator_agent.py:23]

  User Prompt Recipe : JSON array of CellTypeEntry — output of expand_full_names

  Output Schema:
    input_name  str       Original annotation name
    text        str       Text span used for CL search
    cl_id       str|None  Cell Ontology ID (or "NO MATCH found")
    cl_label    str|None  CL label

── Validation  (--run-validation) ───────────────────────────────
Tests whether grounded terms are more/less granular than source CL annotation.
Source CL annotation is withheld from the workflow.
  improved    Agent grounded to a more specific descendant term
  identical   Agent matched author CL exactly
  regression  Agent grounded to a broader ancestor
  no_match    Agent returned NO MATCH
  Reports: filtered_granularity | improved_examples | raw_stats

Settings:  batch_size=4  test_mode=True  test_annotations_count=25
           vector_store=off  embedding_model=text-embedding-3-small
Resources: /Users/do12/.../amica/resources
```

## Changes to `src/amica/dry_run.py`

- `_indent()` → keep as-is
- `describe_pipeline()`:
  - Keep lazy imports (circular import fix)
  - Replace `json.dumps(Model.model_json_schema())` with `_compact_schema(Model)`
  - New helper `_compact_schema(model) -> str`: iterates `model.model_fields`,
    formats as `name  type  description` table
  - Replace full prompt text with first non-empty paragraph + `[N lines, path]`
  - New helper `_prompt_summary(text, source_path) -> str`
  - Layout: show only `resources_dir`, drop derived paths
  - Add validation section (static text, always shown)
  - Add `Aim:` header line

## Test changes (`tests/unit/test_dry_run.py`)

- Remove tests that check for `{` / `}` in output (schema is now tabular)
- Add `test_describe_pipeline_schema_is_tabular`: assert `anyOf` NOT in output
- Existing content checks (node IDs, prompt fragments, settings, paths) remain
- Add `test_describe_pipeline_has_aim_header`
- Add `test_describe_pipeline_has_validation_section`

## Critique

- `_prompt_summary` using "first paragraph" is fragile if prompts are
  reformatted; prefer explicit `# Summary` section in prompt files instead
  (future-proofing once prompts move to external files)
- Compact schema drops `$defs` nesting info — fine for human reading,
  not suitable as a machine-readable spec (keep `model_json_schema()` for that)
