# Expansion Prompt — Cell Type Name Expansion

> **Tunable file.** Edit between iterations and commit each change for audit
> trail.

## Goal

For each annotation label, extract exactly what the paper says about that cell
type and encode it in a structured record. Do not use external knowledge.

---

## Extraction Rules

### `full_name`

Apply the following logic in order:

1. If the label (e.g. `SI_TA`) is defined directly and explicitly in the paper
   (e.g. "SI_TA: small intestinal transit amplifying cell"), use that definition
   verbatim.
2. If the label is a compound abbreviation, check whether each component is
   separately defined in the paper and assemble the full name from the parts
   (e.g. `C_` = "colonic", `EEC` = "enteroendocrine cell" → "colonic
   enteroendocrine cell").
3. If only a prefix is defined (e.g. `C_` = "colonic"), expand the prefix and
   append the remaining suffix as-is.
4. If a single component is defined, use just that component.
5. If nothing is defined, leave `full_name` as `null`.

### `paper_synonyms`

Include only synonyms that appear explicitly in the paper — e.g. via
abbreviation expansion lists, parenthetical definitions, or "also known as"
statements. Separate multiple synonyms with semicolons. Leave `null` if none.

### `tissue_context`

Quote the exact tissue or anatomical term(s) from the paper where this cell
type was identified (e.g. "colon", "small intestine", "follicle-associated
epithelium"). Use the paper's exact wording. Leave `null` if not stated.

---

## Search Strategy

For each label, check the following paper locations in order:

1. Abbreviation or nomenclature tables (often in supplementary materials)
2. Figure legends and cluster annotation notes
3. Results section where cell types are first introduced
4. Methods section (cell type assignment or annotation subsection)
5. Abstract (may name major cell types)

If a label is not found after checking all locations, mark it `UNMAPPABLE` with
a brief reason (e.g. "label not defined in paper or supplementary materials").

---

## Output Format

Return a JSON array. See `output-format.md` for the full schema and examples.

```json
[
  {
    "name": "C_EEC",
    "full_name": "colonic enteroendocrine cell",
    "paper_synonyms": "EEC",
    "tissue_context": "colon"
  },
  {
    "name": "SI_FAE",
    "full_name": "small intestinal follicle-associated epithelium cell",
    "paper_synonyms": "FAE",
    "tissue_context": "follicle-associated epithelium of small intestine"
  },
  {
    "name": "MYSTERY_XYZ",
    "full_name": null,
    "paper_synonyms": null,
    "tissue_context": null,
    "unmappable_reason": "label not found in paper text or supplementary materials"
  }
]
```
