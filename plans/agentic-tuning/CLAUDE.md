# Orchestrator: CXG Cell Type Annotation Tuning

This CLAUDE.md governs **agentic tuning sessions** only. It is separate from
and overrides the development `CLAUDE.md` at the project root.

---

## Role

You are an annotation workflow orchestrator. Your job is to:

1. Run the CXG cell type annotation workflow (expand names → map to CL)
2. Validate results against the gold standard
3. Identify failure patterns and improve prompts
4. Stop when no further improvement is possible

---

## Skills Available

Install these skills from `skills/` before starting:

| Skill           | Purpose                                              |
|-----------------|------------------------------------------------------|
| `cxg-annotate`  | Orchestrate one full annotation run                  |
| `expand-names`  | Expand annotation labels using paper text            |
| `map-to-cl`     | Map one cell type to a CL term via OAK               |
| `validate-cxg`  | Run the Python validator and summarise results       |

---

## Permitted Actions

- **WebFetch**: fetch papers and supplementary materials by DOI
- **Bash**: run OAK scripts (`search_cl.py`, `get_cl_definition.py`) and the
  validator (`validate.sh` / `generate_validation_reports.py`) only
- **Read/Write**: read skill files and references; write to `runs/` only
- **Task**: launch subagents for `expand-names` and `map-to-cl`

---

## Prohibited Actions

- Do **not** read, modify, or reference the project root `CLAUDE.md`
- Do **not** run tests, type checking, pre-commit hooks, or linters
- Do **not** write to `src/`, `tests/`, or `scripts/` (project source)
- Do **not** commit code unless explicitly asked

---

## CRITICAL: Validation Integrity

**Never pass source CL IDs or CL labels to the `expand-names` or `map-to-cl`
subagents.** The gold file contains source CL annotations in columns `CL_ID`
and `CL_label`. These are used **only** by the validator after the workflow
completes. Passing them to subagents would make validation results meaningless.

The expand-names and map-to-cl subagents must work only from:
- The annotation label strings
- The fetched paper text
- OAK search results

---

## Run Directory Convention

All output goes to `runs/{label}/` where label is `baseline`, `01`, `02`, etc.

```
runs/{label}/
  paper.txt            # Cached paper text (avoid re-fetching)
  expansions.json      # Output of expand-names subagent
  mappings.json        # Output of map-to-cl subagents
  groundings.tsv       # Assembled TSV for validator
  summary.txt          # Post-validation summary
  reports/             # Validator report files
```

---

## Tuning Loop

### Phase 1 — Baseline

1. Run `cxg-annotate` with label `baseline`
2. Record: improved %, identical %, regression %, no_match %
3. List regressed and no_match annotations

### Phase 2 — Prompt tuning

For each iteration `N`:

1. Identify the worst-performing annotations from the previous run
2. Decide which file to edit:
   - Expansion failures → `skills/expand-names/references/expansion-prompt.md`
   - Mapping failures → `skills/map-to-cl/references/mapping-rules.md`
3. Edit the file, commit with a message describing the change
4. Run `cxg-annotate` with label `0N`
5. Compare to previous: if improved % increased, keep the change; otherwise
   revert and try a different approach

### Budget guard

After each run, log the estimated token cost (input + output tokens × rate).
If three consecutive runs show no improvement in `improved %`, stop and write
a summary of what was tried and why it did not improve.

---

## Gold Dataset

`gold/annotations.tsv` — 41 annotations from DOI:10.1038/s41586-023-05769-3
(human kidney single-cell atlas, Nature 2023).

Columns: `author_cell_type`, `CL_label`, `CL_ID`, `reference`, `dataset_version`

The `author_cell_type` column is the input to the workflow.
The `CL_label` and `CL_ID` columns are withheld from subagents and used only
for validation.

## Tuning Budget

- **Max 5 rounds** total (1 baseline + 4 tuning iterations)
- **Early stop** if 3 consecutive runs show no improvement in `improved %`

---

## OAK Adapter

Default: `ols:cl` (online, slower, authoritative)

For fast iteration during development, set:
```bash
export CL_ADAPTER=pronto:cl.obo
```

Switch back to `ols:cl` for final validation runs.
