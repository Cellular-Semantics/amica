---
name: map-to-cl
description: Maps a single cell type (full name + synonyms) to a Cell Ontology term using OAK search. Use when given a cell type entry with a full name and synonyms and asked to "find the CL ID", "map to Cell Ontology", "ground to CL", or "look up ontology term".
---

# map-to-cl

Map one cell type to its best Cell Ontology (CL) term. Run all search
strategies below before concluding no_match. Selection rules are in
`references/mapping-rules.md`.

## Inputs

- `name` — original annotation label
- `full_name` — expanded name from paper (may be null)
- `paper_synonyms` — semicolon-separated synonyms from paper (may be null)
- `tissue_context` — anatomical context from paper (may be null)
- `tissue` — tissue from gold metadata (e.g. `kidney`; may be null)

## Search strategy — run ALL steps, collect ALL candidates

**Step 1 — Direct search**

```
scripts/search_cl.py "{full_name}"
scripts/search_cl.py "{name}"
```

**Step 2 — Synonym search**

For each entry in `paper_synonyms`, search individually:
```
scripts/search_cl.py "{synonym}"
```

**Step 3 — Syntactic rearrangements**

CL labels often use "X of Y" and "Y X" as equivalent forms. Generate and
search both:
- "kidney collecting duct cell" → "collecting duct cell of kidney"
- "collecting duct intercalated cell" → "intercalated cell of collecting duct"
- Terms containing "renal" → also try "kidney" substitution (and vice versa)

Generate the rearranged forms yourself, then search each:
```
scripts/search_cl.py "{rearranged_form_1}"
scripts/search_cl.py "{rearranged_form_2}"
```

**Step 4 — Word and phrase substitutions**

Replace words and phrases with common synonymous alternatives and re-search.
Use your general knowledge of cell biology language — not just ontology
synonyms, but the full range of equivalent terms used in literature:

Examples of substitutions to try:
- State/condition prefixes that don't change cell identity: drop "degenerative",
  "cycling", "adaptive", "maladaptive", "transitional", "activated"
  → e.g. "Degenerative Fibroblast" → "fibroblast"
- Equivalent descriptors: "myofibroblast" ↔ "myoid fibroblast", "smooth
  muscle-like fibroblast"; "pericyte" ↔ "perivascular cell", "mural cell"
- Activation state synonyms: "M2 macrophage" ↔ "alternatively activated
  macrophage", "anti-inflammatory macrophage"
- Abbreviation expansions not in paper synonyms, e.g. "pDC" → "plasmacytoid
  dendritic cell"; "IC" → "intercalated cell"; "PC" → "principal cell"
- Tissue synonyms: "renal" ↔ "kidney"; "colonic" ↔ "colon"
- Structural synonyms: "of epithelium of" ↔ "of"; "tubule" ↔ "tubular"

Apply up to 3 substitution rounds, searching after each that yields a new term.

**Step 5 — Tissue-qualified filter**

If `tissue` is provided, get the set of CL terms that have an inferred
`part_of` or `located_in` relationship to the tissue via ubergraph:

```
scripts/filter_by_tissue.py "{tissue}"
```

This outputs a list of CL IDs (one per line). **Prefer** any candidate from
Steps 1–4 whose CL ID appears in this set. Candidates outside the set are not
excluded but are demoted relative to tissue-matched candidates.

**Step 6 — Definition comparison (top 3 candidates)**

For the top 3 candidates after Steps 1–5, fetch the OAK definition:
```
scripts/get_cl_definition.py {cl_id}
```

Compare definition text to `full_name`, `paper_synonyms`, and `tissue_context`.
A candidate whose definition explicitly mentions the same tissue and cell
function as the input should be strongly preferred even if its lexical rank
is lower. See `references/mapping-rules.md` Rule 2.

## Output

```json
{
  "input_name": "aFIB",
  "cl_id": "CL:1000692",
  "cl_label": "kidney interstitial fibroblast",
  "match_type": "exact"
}
```

`match_type`: `exact` | `broad` | `no_match`

Only return `no_match` after exhausting ALL steps above.
