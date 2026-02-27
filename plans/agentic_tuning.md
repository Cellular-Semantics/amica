# Agentic CXG Annotation Tuning

## Functional Spec

> Given cell type annotation names as input, extract sufficient information
> from the paper to map to cell types in CL, and indicate whether the mapping
> is exact or broad.
>
> Steps:
> 1. Map annotation names → full names + synonyms via paper context
> 2. Map full names + synonyms → CL term via OAK
>
> Output: annotation_text, full_name, synonyms, cl_id, cl_label (TSV)
>
> Validation: are grounded terms more/less granular than the source CL
> annotation? More granular = improved. Source CL withheld from workflow.

---

## Architecture

The workflow runs almost entirely in Claude's context. The only Python code
used is OAK (via a thin wrapper script) and the existing validator.

```text
Orchestrator  (cxg-annotate skill)
  │
  ├─ [1] Paper retrieval
  │       WebFetch paper + supplementary materials by DOI.
  │       If supp matt is Excel: run scripts/extract_excel.py → plain text.
  │
  ├─ [2] Name expansion subagent  (expand-names skill)
  │       Given: annotation name list + paper/supp context
  │       Loop until: all names mapped OR marked unmappable
  │       Output: TSV with name, full_name, synonyms, tissue_context
  │       Prompt: references/expansion-prompt.md  (tunable)
  │
  ├─ [3] Parallel CL mapping subagents  (map-to-cl skill, one per annotation)
  │       Given: full_name, synonyms for one annotation
  │       Calls: scripts/search_cl.py  (OAK wrapper)
  │       Tuning v2: also fetch OAK definition for top candidates and use
  │         definition text to verify match makes biological sense
  │       Output: cl_id, cl_label, match_type
  │
  └─ [4] Orchestrator assembles TSV, calls validator
          uv run python scripts/generate_validation_reports.py \
            --raw-output-dir runs/{n}/ --reports-dir runs/{n}/reports/
          Reports: improved / identical / regression %
```

---

## Skill Structure

Each skill is a folder with `SKILL.md` (YAML frontmatter + instructions).
All skill folders live under `plans/agentic-tuning/skills/` during development;
install to the Claude Code skills directory to activate.

### `cxg-annotate/` — Orchestrator

```
cxg-annotate/
  SKILL.md
  scripts/
    extract_excel.py   # Extract supplementary Excel → plain text
  references/
    output-schema.md   # TSV column spec + example row
```

SKILL.md frontmatter:
```yaml
---
name: cxg-annotate
description: Annotates CXG cell type labels by mapping them to Cell Ontology
  terms using source publication text. Use when asked to "annotate CXG data",
  "run cell type annotation", or "map cell type labels to CL".
---
```

Pattern: **Sequential workflow orchestration** (Pattern 1 from guide) with
an **Iterative refinement** loop on the expansion step (Pattern 3).

### `expand-names/` — Name Expansion Subagent

```
expand-names/
  SKILL.md
  references/
    expansion-prompt.md   # Full expansion prompt (tunable)
    output-format.md      # TSV column spec + examples
```

SKILL.md frontmatter:
```yaml
---
name: expand-names
description: Extracts full cell type names and synonyms from academic paper
  text for a list of annotation labels. Use when given annotation names and
  paper content and asked to expand or resolve cell type labels.
---
```

Instructions: read `references/expansion-prompt.md` before starting.
Loop: process all annotation names; mark any as UNMAPPABLE if not found;
do not stop until all are resolved or marked.

### `map-to-cl/` — CL Mapping Subagent

```
map-to-cl/
  SKILL.md
  scripts/
    search_cl.py        # OAK search_cl wrapper: returns (cl_id, label, score)
    get_cl_definition.py  # OAK fetch definition text for a CL ID
  references/
    mapping-rules.md    # Selection heuristics (tunable)
```

SKILL.md frontmatter:
```yaml
---
name: map-to-cl
description: Maps a single cell type (name + synonyms) to a Cell Ontology
  term using OAK. Use when given a CellTypeEntry and asked to find the CL ID.
---
```

Instructions:
1. Run `scripts/search_cl.py "{full_name}"` → candidate list
2. If no confident match, try each synonym
3. **[Tuning v2]** For top 3 candidates, run `scripts/get_cl_definition.py
   {cl_id}` and compare definition text to the annotation context
4. Apply rules from `references/mapping-rules.md` to select best match
5. Return: cl_id, cl_label, match_type (exact | broad | no_match)

### `validate-cxg/` — Validator (thin wrapper)

```
validate-cxg/
  SKILL.md
  scripts/
    validate.sh         # Calls uv run python scripts/generate_validation_reports.py
```

---

## Orchestrator Configuration

The orchestrator runs in a Claude Code session with a **separate CLAUDE.md**
(`plans/agentic-tuning/CLAUDE.md`) — not the dev CLAUDE.md.

Key rules for orchestrator CLAUDE.md:
- Role: run and improve the CXG cell type annotation workflow
- Permitted: WebFetch (papers), Bash (OAK scripts + validator only),
  write to `plans/agentic-tuning/runs/`
- NOT bound by dev rules (no TDD, no pre-commit, no type checking)
- CRITICAL: do not pass source CL annotations to expand-names or map-to-cl
- Budget guard: log estimated cost per run; stop if no improvement after 3 iterations

---

## File Layout

```text
plans/agentic-tuning/
  CLAUDE.md                        # Orchestrator config (separate from dev)
  skills/
    cxg-annotate/
      SKILL.md
      scripts/
        extract_excel.py
      references/
        output-schema.md
    expand-names/
      SKILL.md
      references/
        expansion-prompt.md        # Tunable — edit between iterations
        output-format.md
    map-to-cl/
      SKILL.md
      scripts/
        search_cl.py
        get_cl_definition.py       # Added for tuning v2
      references/
        mapping-rules.md           # Tunable — edit between iterations
    validate-cxg/
      SKILL.md
      scripts/
        validate.sh
  gold/
    annotations.tsv                # Gold dataset: names + DOIs + source CL
  runs/
    baseline/                      # First run output + validation report
    01/                            # Iteration 1
    02/                            # Iteration 2 (etc.)
```

---

## Tuning Loop

### Phase 1: Basic functionality (MVP)

1. Retrieve paper + supp for 1 DOI (manual WebFetch or cached text file)
2. Run `expand-names` → inspect TSV coverage (any UNMAPPABLE?)
3. Run `map-to-cl` in parallel for each row → assemble TSV
4. Run `validate-cxg` → read improved/regression %
5. Save to `runs/baseline/`

### Phase 2: Prompt tuning (manual)

6. Identify worst-performing annotations (no_match or regression)
7. Edit `references/expansion-prompt.md` or `references/mapping-rules.md`
8. Re-run from step 2, save to `runs/01/`
9. Compare: if improved %, keep changes; else revert

### Phase 3: OAK definition enrichment (tuning v2)

10. Enable `get_cl_definition.py` calls in `map-to-cl`
11. Run baseline comparison: does definition context improve improved %?
12. If yes, tune the definition-comparison logic in mapping-rules.md

### Phase 4: Automated loop (v3)

13. Orchestrator proposes prompt edits based on failure patterns
14. Iterates automatically, stops when no improvement over 3 runs

---

## MVP Scope

- 1 paper, ~20 annotations with known source CL
- Cached paper text (skip live WebFetch for speed)
- Manual orchestration (operator runs each skill step by step)
- Success criterion: baseline improved % > 0; expansion coverage = 100%

---

## Progress

### Baseline run complete (2026-02-21)

**Dataset:** 41 annotations from DOI:10.1038/s41586-023-05769-3 — human kidney
single-cell atlas (Nature 2023). Switched from original 11-annotation intestinal
atlas to this larger, more challenging set.

**Current workflow (end-to-end):**

1. **Paper retrieval** — `PublicationFetcher` (existing Python infra) downloads
   full text via PubMed BioC / Unpaywall / DOI fallback chain. Cached to
   `resources/publications/`. Copied into `runs/baseline/paper.txt` (152 KB).

2. **Name expansion** — `expand-names` subagent reads paper text + 41 annotation
   labels. Extracts `full_name`, `paper_synonyms`, `tissue_context` for each.
   Rules: direct definitions first, then compound abbreviation assembly, then
   prefix expansion. Labels not found marked UNMAPPABLE.
   - Result: **34 resolved (83%), 7 UNMAPPABLE**.
   - UNMAPPABLE labels: IC-B, Intercalated Cell Type B, Medullary Fibroblast,
     C-IC-A, CNT-IC-A, Connecting Tubule Intercalated Cell Type A, dC-IC-A.
   - These were still passed to mapping with fallback search terms.

3. **CL mapping** — `map-to-cl` subagents (batched, 5 per batch) call
   `search_cl.py` (OAK, `ols:cl` adapter) then `get_cl_definition.py` for
   top candidates. Selection via `mapping-rules.md` heuristics.
   - Note: OLS adapter returned no definitions for any CL term tested.
     Definition-based verification was therefore not available for baseline.

4. **Assembly** — Python script joins mappings + gold file → `groundings.tsv`.

5. **Validation** — `generate_validation_reports.py` compares grounded CL terms
   against gold CL annotations using ontology ancestor/descendant checks.

**Baseline results:**

| Category                 | Count | %      |
|--------------------------|-------|--------|
| Improved Granularity     |     8 | 19.5%  |
| Identical Mapping        |    13 | 31.7%  |
| Regression               |     2 |  4.9%  |
| No Match                 |     0 |  0.0%  |
| Other / Different Branch |    18 | 43.9%  |

### Preliminary findings

The **"Other / Different Branch" category (18/41, 44%)** dominates. These are
cases where the agent's grounding is on a different CL branch than the gold
standard, so the validator cannot classify them as improved or regressed. Key
patterns:

1. **Generic vs kidney-specific CL terms.** The agent mapped to canonical
   generic terms while gold uses kidney-qualified terms:
   - `M2 Macrophage` → `CL:0000890 M2 macrophage` (generic)
     vs gold `CL:1000695 kidney interstitial alternatively activated macrophage`
   - `Myofibroblast` → `CL:0000186 myofibroblast cell` (generic)
     vs gold `CL:1000692 kidney interstitial fibroblast` (different lineage)

2. **VSMC/pericyte composite labels.** All 8 VSMC-related annotations map to
   `CL:1001318 renal interstitial pericyte` in gold, but the agent chose
   `CL:0000359 vascular associated smooth muscle cell`. The gold convention
   is to use the pericyte branch for these composites.

3. **Domain-specific mapping conventions.** Some gold mappings reflect CXG
   curation decisions rather than direct ontology lineage:
   - `REN` (renin granular cell) → gold: `CL:1001318 renal interstitial pericyte`
   - `Macula Densa Cell` → gold: `CL:1001106 kidney loop of Henle thick
     ascending limb epithelial cell`

4. **OAK definition lookup failure.** The `ols:cl` adapter returned no
   definitions for any tested CL ID. This disabled Rule 2 (definition-based
   match confirmation) entirely. Switching to `pronto:cl.obo` may help.

---

## Roadmap

### Blocked: Enrich gold standard inputs (manual — @owner)

Before further tuning, the gold dataset needs richer metadata per annotation:

- **Tissue** (UBERON term) — anatomical context for each annotation
- **Stage** (HsapDv term) — developmental stage if applicable
- **Annotation hierarchy** — parent/child relationships between the 41 labels
  (e.g. `dFIB` is a state of `FIB`; `C-IC-A` is a subtype of `IC`)
- **Match type** — whether each gold CL mapping is `exact` or `broad` relative
  to the author's intended cell type

This enrichment is currently a manual step. In future it may be automated by
querying the CXG knowledge graph or UBERON/HsapDv via OAK.

**Output:** enriched `gold/annotations.tsv` with additional columns:
`uberon_id`, `uberon_label`, `hsapdv_id`, `hsapdv_label`,
`parent_annotation`, `gold_match_type`

### Phase 2: Prompt tuning (blocked by enriched inputs)

Once richer inputs are available:

1. Update `expand-names` prompt to use tissue/stage context
2. Update `map-to-cl` mapping rules to incorporate hierarchy and match type
3. Re-run tuning loop (max 5 rounds total: 1 baseline + 4 iterations)
4. Early stop if 3 consecutive runs show no improvement

### Phase 3: OAK definition enrichment

- Switch to `pronto:cl.obo` adapter to get definitions
- Re-evaluate definition-based match verification (Rule 2)
- Tune definition-comparison logic in `mapping-rules.md`

### Phase 4: Automated loop

- Orchestrator proposes prompt edits based on failure patterns
- Iterates automatically, stops after 3 stagnant runs

---

## Critique / Risks

- **OAK speed**: `ols:cl` is slow; use `pronto:` local adapter for fast
  iteration, `ols:cl` only for final eval
- **OAK definitions**: `ols:cl` returned no definitions — `pronto:cl.obo`
  should be tested as alternative
- **Parallelism cap**: parallel `map-to-cl` subagents may hit rate limits;
  start sequential, parallelise once stable
- **Validation circularity**: source CL must stay withheld; orchestrator
  CLAUDE.md must explicitly prohibit passing it to subagents
- **"Other" category ambiguity**: the validator's "Other / Different Branch"
  bucket conflates genuine errors with reasonable alternative groundings.
  Enriched gold metadata (match type, hierarchy) should help disambiguate.
- **Excel extraction**: `extract_excel.py` should be minimal (openpyxl,
  output plain TSV); avoid scope creep
- **Prompt files in git**: editing `expansion-prompt.md` between runs creates
  a natural audit trail — use git commits to checkpoint each iteration
- **Context size**: paper text can be large; use vector store or chunking if
  expansion subagent context overflows (integrate existing DocumentVectorStore
  if needed)
