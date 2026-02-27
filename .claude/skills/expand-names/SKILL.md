---
name: expand-names
description: Extracts full cell type names, synonyms, and tissue context from academic paper text for a list of annotation labels. Use when given annotation labels and paper content and asked to "expand annotation names", "resolve cell type labels", "find full names from paper", or "map shorthand labels to full cell type names".
---

# expand-names

Read `references/expansion-prompt.md` before starting — it contains the full
extraction logic and output rules.

## Inputs

- A list of annotation label strings (e.g. `C_EEC`, `SI_FAE`, `paneth`)
- Paper text (full text or excerpts) and/or supplementary material text

## Task

For **every** annotation label in the input list:

1. Search the paper text for direct definitions, abbreviation lists, figure
   captions, and methods sections.
2. Expand the label into `full_name`, `paper_synonyms`, and `tissue_context`
   following the rules in `references/expansion-prompt.md`.
3. If a label cannot be resolved after exhaustive search, mark it `UNMAPPABLE`
   with a brief reason.

Do **not** stop until every label is either resolved or marked `UNMAPPABLE`.
Do **not** use external knowledge — all output must come from the provided text.

## Output

Return a JSON array of objects. Each object must follow the schema in
`references/output-format.md`.

```json
[
  {
    "name": "C_EEC",
    "full_name": "colonic enteroendocrine cell",
    "paper_synonyms": "EEC",
    "tissue_context": "colon"
  },
  ...
]
```
