# Validation & Reporting

This add-on summarizes how the AMICA agent performed after a CXG run completes. It
inspects the grounded outputs written under `output/raw_output/**/groundings.tsv`
and the curated match-type tables from `output/pandasaurus_cxg_outputs_30/*.tsv`.

## Usage

```bash
uv run scripts/generate_validation_reports.py \
  --output-root ./output \
  --log-level INFO
```

By default the script writes three Markdown summaries into `output/reports/`:

| File | Description |
|------|-------------|
| `filtered_granularity_report.md` | Aggregated stats that ignore `Broad term` / `Overlaps` rows.|
| `raw_stats_report.md` | Unfiltered counts (improved / identical / regressions / no-match) for every grounding row. |
| `granularity_report.md` | Narrative examples showcasing rows where the agent improved on the author label. |


## CLI options

```
usage: scripts/generate_validation_reports.py [-h] [--output-root OUTPUT_ROOT]
                                              [--raw-output-dir RAW_OUTPUT_DIR]
                                              [--match-type-dir MATCH_TYPE_DIR]
                                              [--reports-dir REPORTS_DIR]
                                              [--skip-filtered]
                                              [--skip-examples]
                                              [--skip-raw-stats]
                                              [--skip-ontology]
                                              [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
```

Key flags:

- `--output-root`: base directory that contains `raw_output/`, `pandasaurus_cxg_outputs_30/`, and `reports/`. Defaults to `resources/cxg/output`. Set this when your outputs sit under a different base (e.g., top-level ./output)
- `--raw-output-dir`: direct path to per-dataset `groundings.tsv` (AMICA raw outputs). Overrides `--output-root` for groundings. Use when groundings live outside the standard layout. **If missing:** script exits with `FileNotFoundError`.
- `--match-type-dir`: direct path to the Pandasaurus match-type TSV/CSV files. Use when those files live elsewhere; overrides `--output-root` for match types only. **If missing:** script exits with `FileNotFoundError`; missing individual dataset files are tolerated (that dataset runs without Broad/Overlap filtering).
- `--reports-dir`: output directory for markdown reports (auto-created if needed). Defaults to `<output-root>/reports`.

## Skip toggles

- `--skip-filtered`, `--skip-raw-stats`, `--skip-examples`: toggle which reports are generated.
- `--skip-filtered`: do not generate the filtered granularity report (excludes "Broad term"/"Overlaps"). Use when only raw stats are needed.
- `--skip-raw-stats`: do not generate the unfiltered aggregate stats report. Use when only filtered or example reports are needed.
- `--skip-examples`: do not generate the “improved examples” report. Use when only aggregate statistics are required.
- `--skip-ontology`: runs without Cell Ontology lookups. This prevents network calls and allows offline runs, but any metric that depends on the hierarchy (improved vs regression, example extraction) will be degraded: rows that should be "improved" or "regression" are instead categorized as "other", and no examples are extracted. Reports include a warning banner. For accurate stats, leave ontology enabled or point to a local ontology via `--ontology-adapter` (e.g., `pronto:/path/to/cl.owl`).
- `--ontology-adapter`: use a custom oaklib adapter string (e.g., `pronto:/path/to/cl.owl`) for offline runs. Defaults to `ols:cl`.

## Dependencies

The script reuses AMICA's `oaklib` dependency to talk to the Cell Ontology
through OLS. Make sure the machine has outbound network access when you want
hierarchy-aware stats; otherwise pass `--skip-ontology` to generate degraded
reports without ontology calls.
