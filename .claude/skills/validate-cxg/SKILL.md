---
name: validate-cxg
description: Validates a CXG annotation groundings TSV against source CL annotations and generates improvement reports. Use when asked to "validate groundings", "run the validator", "check annotation quality", or "generate validation reports".
---

# validate-cxg

Run the existing Python validator on a groundings TSV and return a summary of
results.

## Inputs

- `--raw-output-dir`: directory containing `groundings.tsv` (e.g.
  `runs/baseline/`)
- `--reports-dir`: directory to write reports to (e.g. `runs/baseline/reports/`)

## Steps

Run:

```bash
scripts/validate.sh <raw-output-dir> <reports-dir>
```

Then read the reports directory and summarise the results.

## Output summary

Report the following metrics:

| Outcome    | Meaning                                               |
|------------|-------------------------------------------------------|
| improved   | Agent grounded to a more specific descendant term     |
| identical  | Agent matched author CL exactly                       |
| regression | Agent grounded to a broader ancestor                  |
| no_match   | Agent returned NO MATCH                               |

Also list the annotation labels that regressed or returned no_match, so the
orchestrator can target prompt improvements.
