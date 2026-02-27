# Output Schema — groundings.tsv

The output TSV must be tab-separated with the following columns in order.
This format matches what the Python validator (`generate_validation_reports.py`)
expects.

## Columns

| Column               | Source                          | Notes                                                   |
|----------------------|---------------------------------|---------------------------------------------------------|
| `dataset_name`       | fixed                           | `dataset_version` value from gold file                  |
| `annotation_text`    | gold `author_cell_type`         | Original annotation label, unchanged                    |
| `article_id_doi`     | gold `reference`                | DOI string, e.g. `DOI:10.1038/s41586-023-05769-3`      |
| `cl_id`              | gold `CL_ID`                    | Source CL ID (for validator, not used by subagents)     |
| `cl_label`           | gold `CL_label`                 | Source CL label (for validator, not used by subagents)  |
| `grounding_cl_id`    | map-to-cl output `cl_id`        | Grounded CL ID; empty if `no_match`                     |
| `grounding_cl_label` | map-to-cl output `cl_label`     | Grounded CL label; empty if `no_match`                  |
| `enrichment`         | leave blank                     | Not used in current workflow                            |
| `result`             | leave blank                     | Filled in by the validator                              |

## Gold metadata columns (available to orchestrator; withheld from subagents)

These columns are in `gold/annotations.tsv` but must NOT be included in
`groundings.tsv` and must NOT be passed to `expand-names` or `map-to-cl`:

| Column            | Use                                                         |
|-------------------|-------------------------------------------------------------|
| `CL_ID`           | Validation target — withheld                                |
| `CL_label`        | Validation target — withheld                                |
| `gold_match_type` | `direct` or `broad`; for validation context only            |

## Gold metadata columns (safe to pass to subagents)

| Column           | Pass to         | Purpose                                          |
|------------------|-----------------|--------------------------------------------------|
| `parent_cluster` | expand-names    | Helps locate cell type in paper sections         |
|                  | map-to-cl       | Provides lineage context for candidate selection |
| `tissue`         | map-to-cl       | Used for tissue filter (`filter_by_tissue.py`)   |
|                  | expand-names    | Sets expected tissue context in output           |

## Example row

```
dataset_name	annotation_text	article_id_doi	cl_id	cl_label	grounding_cl_id	grounding_cl_label	enrichment	result
0b75c598-..._cxg_dataset_unique	IC-B	DOI:10.1038/s41586-023-05769-3	CL:1001432	kidney collecting duct intercalated cell	CL:1001432	kidney collecting duct intercalated cell
```

## Notes

- Use tab (`\t`) as delimiter; no quoting needed unless a field contains a tab.
- The header row is required.
- All 41 gold annotations must appear in the output (one row each).
- `grounding_cl_id` and `grounding_cl_label` may be empty for `no_match` cases.
