# OLS4 / OAK Search API Research Findings

*Recorded before context compression — 2026-02-23*

---

## Context

Investigating the best approach for CL term search in the `map-to-cl` skill,
following a baseline run where 44% of annotations fell into "Other/Different
Branch" — primarily because the workflow mapped to generic CL terms instead of
kidney-qualified ones, and OAK definitions silently returned `None`.

---

## OAK Adapter Summary

| Adapter | `basic_search()` | `definition()` | Relationship queries | Notes |
|---------|-----------------|----------------|---------------------|-------|
| `ols:cl` | Solr full-text, fast, synonym-aware | **Returns `None` silently** | Untested | Legacy OLS endpoint |
| `ubergraph:` | SPARQL regex — slower, label-only | **Works, returns full text** | ✓ Transitive closures | Good for definitions + tissue filter |
| `pronto:cl.obo` | Fast local | Works | Works | Needs local .obo file download |

### Key finding: `ols:cl` definition failure
`definition()` returns `None` for every CL term via OAK's OLS adapter. This
silently disabled Rule 2 (definition-based match confirmation) throughout the
entire baseline run. This was the primary tuning mechanism that never fired.

---

## OLS4 REST API vs MCP Comparison

Tested query: `"intercalated cell kidney"` (representative difficult case).

### REST API `/api/search` (legacy Solr endpoint)
- Classic Solr BM25/tf-idf ranking
- Prioritises terms with all keywords **literally in the label**
- `CL:1001432 kidney collecting duct intercalated cell` → **rank 20**
- No obsolete terms in top 20
- Returns `description` and `exact_synonyms` inline — **no separate definition call needed**
- No scores exposed in response

### OLS4 MCP (`searchClasses`, ontologyId=cl)
- Uses OLS4 v2 ranking (different algorithm)
- `CL:1001432 kidney collecting duct intercalated cell` → **rank 3**
- Surfaces broader/parent terms higher; considers definitions/synonyms in ranking
- Returns `CL:0700009` (obsolete) at rank 2 — needs `isObsolete=false` filter
- Better for our use case: parent cluster terms appear at useful ranks

### Raw REST API response structure
```json
{
  "obo_id": "CL:4030005",
  "label": "kidney collecting duct beta-intercalated cell",
  "description": ["A renal beta-intercalated cell that is part of the cortical collecting duct..."],
  "exact_synonyms": ["B-IC", "kidney collecting duct intercalated cell type B"],
  "type": "class"
}
```
**Definitions and synonyms are inline** — no separate lookup step needed if
using the REST API or MCP directly.

---

## OLS Search Behaviour Examples

| Query | Top result | Target in results? |
|-------|------------|-------------------|
| `aFIB` | No results | — |
| `kidney interstitial fibroblast` | `CL:1000692` ✓ | Rank 1 |
| `M2 macrophage` | `CL:0000890` (generic) | `CL:1000695` **absent** |
| `renal interstitial pericyte` | `CL:1001318` ✓ | Rank 1 |
| `intercalated cell kidney` | `CL:4030005` (subtype) | `CL:1001432` rank 20 |
| `alternatively activated macrophage` | (not tested) | `CL:1000695` expected |

Key insight: `CL:1000695 kidney interstitial alternatively activated macrophage`
is completely absent from `M2 macrophage` OLS results. OLS does not index "M2"
as a synonym for this term. Step 4 (word substitution: "M2" → "alternatively
activated") is **required** to surface this term.

---

## Recommended Architecture (post-findings)

| Script | Adapter/Endpoint | Rationale |
|--------|-----------------|-----------|
| `search_cl.py` | OLS4 MCP (if available) or REST API direct | MCP gives better ranking for parent terms; REST API returns definitions inline |
| `get_cl_definition.py` | **Deprecated** if using REST API/MCP | Definitions come with search results |
| `filter_by_tissue.py` | `ubergraph:` (keep as-is) | Relationship traversal requires SPARQL |

**Option A (preferred if MCP configured):** Update `map-to-cl/SKILL.md` to use
OLS4 MCP tool for search (with `isObsolete=false`). Drop `search_cl.py` and
`get_cl_definition.py`. Keep `filter_by_tissue.py`.

**Option B (portable):** Rewrite `search_cl.py` to call OLS4 v2 REST endpoint
directly instead of via OAK. Returns definitions inline, better ranking.
Add `--no-obsolete` flag.

**Blocked on:** confirming whether OLS4 MCP is configured in the orchestrator
session (not just dev environment). If yes, go Option A; if no, go Option B.

---

## Pending changes (not yet implemented)

1. Switch `get_cl_definition.py` default from `ols:cl` → `ubergraph:` (minimal
   fix; gives definitions while keeping OLS for search)
2. OR rewrite `search_cl.py` for OLS4 direct (Option B above)
3. Update `map-to-cl/SKILL.md` Step 6 to note definitions come with search
   results if using REST API/MCP directly

---

## Other notes

- `filter_by_tissue.py` already uses `ubergraph:` and is working correctly
- Gold dataset enriched: `parent_cluster`, `tissue`, `gold_match_type` added
- `gold_match_type=direct` for IC and PC (cluster-level); `broad` for all
  subclusters (per project convention)
- Baseline "Other/Different Branch" (44%): expect significant reduction once
  tissue filter fires and definitions are available for Rule 2
