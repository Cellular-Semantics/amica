---
name: cxg-annotate
description: Orchestrates CXG cell type annotation by mapping cell type labels
  to Cell Ontology terms using source publication text. Use when asked to
  "annotate CXG data", "run cell type annotation", "map cell type labels to CL",
  or "run the annotation workflow".
---

# cxg-annotate

Orchestrate the full annotation workflow for one dataset. Reads annotation
labels and metadata from the gold file, fetches the paper, runs name expansion
and CL mapping, assembles the output TSV, and calls the validator.

See `references/output-schema.md` for the full column spec and the
pass/withhold rules for gold metadata fields.

## Inputs

- `gold/annotations.tsv` — annotation labels + metadata + source CL (source CL
  is withheld from subagents; see output-schema.md)
- A run label, e.g. `baseline` or `01` (determines output directory)

## CRITICAL: what to withhold vs pass to subagents

**Withhold** (never pass to expand-names or map-to-cl):
- `CL_ID`, `CL_label`, `gold_match_type`

**Pass freely** (contextual metadata, not answers):
- `parent_cluster` — helps the expand-names subagent locate the annotation in
  the paper, and helps map-to-cl narrow the candidate set
- `tissue` — passed to map-to-cl for the tissue filter step

## Workflow

### Step 1 — Retrieve paper text

Fetch the paper by DOI using WebFetch. Try:
1. The DOI URL directly
2. The PubMed Central full-text URL if the DOI redirects to a paywall
3. Any supplementary material links found in the paper

If supplementary materials are in Excel format, run:
`uv run python scripts/extract_excel.py <file> > supp.txt`

Cache fetched text to `runs/{label}/paper.txt` to avoid re-fetching.

### Step 2 — Name expansion (expand-names subagent)

Launch the `expand-names` skill as a subagent with:
- The annotation name list (`author_cell_type` column from gold)
- The `parent_cluster` value for each annotation (pass as context alongside
  each name — e.g. "IC-B [cluster: IC]")
- The `tissue` value (e.g. "kidney") as overall context
- The fetched paper text

**Do NOT pass `CL_ID`, `CL_label`, or `gold_match_type`.**

Wait for output: JSON array of expanded entries.
Save to `runs/{label}/expansions.json`.

If any entries are `UNMAPPABLE`, log them and continue with the rest.

### Step 3 — CL mapping (map-to-cl subagents, one per annotation)

For each expanded entry, launch a `map-to-cl` subagent. Pass:
- `name`, `full_name`, `paper_synonyms`, `tissue_context` from expansions
- `tissue` from gold (e.g. `kidney`)
- `parent_cluster` from gold (e.g. `Interstitial`, `IC`, `PC`)

Cap at 5 concurrent subagents. Collect results.
Save to `runs/{label}/mappings.json`.

### Step 4 — Assemble output TSV

Join expansions and mappings on `name`. Write `runs/{label}/groundings.tsv`
following the column spec in `references/output-schema.md`.

### Step 5 — Validate

Run the validator:

```bash
uv run python scripts/generate_validation_reports.py \
  --raw-output-dir runs/{label}/ \
  --reports-dir runs/{label}/reports/
```

Read `runs/{label}/reports/` and summarise:
- improved %
- identical %
- regression %
- no_match %
- other/different-branch %

Log the summary to `runs/{label}/summary.txt`.

## Budget guard

After each run, log the estimated token cost. If three consecutive runs show no
improvement in `improved %`, stop and report.
