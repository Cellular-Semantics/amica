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

- `--output-root`: base directory that contains `raw_output/`, `pandasaurus_cxg_outputs_30/`, and `reports/`. Defaults to `resources/cxg/output`.
- `--raw-output-dir`, `--match-type-dir`, `--reports-dir`: override individual directories if they live elsewhere.
- `--skip-filtered`, `--skip-examples`, `--skip-raw-stats`: toggle which reports are generated.
- `--skip-ontology`: skip the online OLS lookup entirely.
- `--ontology-adapter`: use a custom oaklib adapter string (e.g., `pronto:/path/to/cl.owl`) for offline runs. Defaults to `ols:cl`.

## Dependencies

The script reuses AMICA's `oaklib` dependency to talk to the Cell Ontology
through OLS. Make sure the machine has outbound network access when you want
hierarchy-aware stats; otherwise pass `--skip-ontology` to generate degraded
reports without ontology calls.
