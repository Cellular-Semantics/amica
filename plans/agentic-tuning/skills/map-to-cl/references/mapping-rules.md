# Mapping Rules — map-to-cl

> **Tunable file.** Edit between iterations and commit each change for audit
> trail. Rules are ordered by priority (Rule 1 = highest).

---

## Rule 1 — Prefer CL over other ontologies

If `search_cl` returns candidates from multiple ontologies, always prefer a
Cell Ontology (CL) term. Reject UBERON, GO, or other ontology terms even if
their lexical score is higher.

---

## Rule 2 — Use definition text to confirm the match (primary quality signal)

For the top 3 candidates, fetch the OAK definition with
`get_cl_definition.py {cl_id}` and compare it to the annotation context:

- Does the definition mention the same tissue as `tissue_context` or `tissue`?
- Does the definition describe the same function or lineage as `full_name`?
- Does the definition use any of the `paper_synonyms`?

A candidate whose definition text aligns with the annotation context should be
strongly preferred, even if its lexical match score is lower.

---

## Rule 3 — Prefer tissue-qualified terms (tissue filter)

If `tissue` is provided and `filter_by_tissue.py` has been run, **strongly
prefer** candidates whose CL ID appears in the tissue-relevant set. These
are terms that the ontology explicitly locates within the tissue via `part_of`
or `located_in` relationships.

Example: for `tissue=kidney`, prefer `CL:1000692 kidney interstitial fibroblast`
over `CL:0000186 myofibroblast cell`, even if the latter scores higher
lexically.

A candidate outside the tissue set is not excluded but is demoted: only select
it if no tissue-matched candidate exists after exhausting all search steps.

---

## Rule 4 — Prefer the most specific matching term

Among tissue-matched candidates, prefer the most specific CL term that is
consistent with the annotation. Avoid over-generalising to a parent term when
a more specific descendant matches.

Exception: if the input is a state-qualified subtype (e.g. "degenerative
fibroblast", "cycling myofibroblast") and no state-qualified CL term exists,
map to the canonical cell type without the state qualifier.

---

## Rule 5 — Penalise activation/marker/species over-specificity

Down-rank candidates that add qualifiers not present in the input:
- Activation state (activated, quiescent, resting)
- Protein marker (CD4-positive, CD8-positive)
- Species restriction (human, mouse) unless input specifies species

---

## Rule 6 — Composite labels: use the dominant cell identity

For composite labels (e.g. "Vascular Smooth Muscle Cell / Pericyte",
"VSMC/P", "tPC-IC"), identify the primary cell identity:
- If the tissue gold metadata maps this cluster to a specific CL term, use that
  as a strong prior for which identity is dominant in this dataset's convention
- Otherwise use the definition comparison (Rule 2) to determine which identity
  the CL candidates best support

---

## Rule 7 — match_type assignment

| Condition                                               | match_type  |
|---------------------------------------------------------|-------------|
| CL definition and tissue closely match input context   | `exact`     |
| CL term is a parent/ancestor of the ideal match        | `broad`     |
| No suitable CL term found after all search strategies  | `no_match`  |

---

## Fallback sequence

If all search steps in SKILL.md yield no tissue-matched candidate:

1. Accept the best non-tissue-matched CL candidate with a supporting definition
2. Assign `match_type: broad`
3. If still nothing, return `no_match` with a note on which steps were tried
