# Output Format — expand-names

## Schema

Each element of the output JSON array must have these fields:

| Field              | Type         | Required | Description                                              |
|--------------------|--------------|----------|----------------------------------------------------------|
| `name`             | string       | yes      | Exact annotation label from input (unchanged)            |
| `full_name`        | string\|null | yes      | Expanded name from paper; null if not found              |
| `paper_synonyms`   | string\|null | yes      | Semicolon-separated synonyms from paper; null if none    |
| `tissue_context`   | string\|null | yes      | Exact anatomical term(s) from paper; null if not stated  |
| `unmappable_reason`| string\|null | no       | Reason if label could not be resolved; omit if resolved  |

## Rules

- Every input label must appear in the output exactly once.
- `name` must be copied verbatim from the input (no normalisation).
- `full_name`, `paper_synonyms`, and `tissue_context` must contain **only**
  information from the provided paper text, not external knowledge.
- If a label is unresolvable, include `unmappable_reason` and set all other
  optional fields to `null`.

## Example

```json
[
  {
    "name": "C_ISC",
    "full_name": "colonic intestinal stem cell",
    "paper_synonyms": "ISC",
    "tissue_context": "colon"
  },
  {
    "name": "C_TA",
    "full_name": "colonic transit amplifying cell",
    "paper_synonyms": "TA cell",
    "tissue_context": "colon"
  },
  {
    "name": "paneth",
    "full_name": "Paneth cell",
    "paper_synonyms": null,
    "tissue_context": "small intestine"
  },
  {
    "name": "UNKNOWN_LABEL",
    "full_name": null,
    "paper_synonyms": null,
    "tissue_context": null,
    "unmappable_reason": "label not defined in paper or supplementary materials"
  }
]
```
