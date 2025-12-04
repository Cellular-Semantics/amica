# CXG Workflow Analysis: Reference Retrieval & Name Expansion

**Date**: 2025-12-04
**Focus**: Steps 1-2 of the CXG annotation pipeline
**Purpose**: Analyze current implementation and propose efficiency improvements

---

## Table of Contents

1. [Current Workflow Overview](#current-workflow-overview)
2. [Step 1: Reference Retrieval](#step-1-reference-retrieval)
3. [Step 2: Name Expansion](#step-2-name-expansion)
4. [Cost Analysis](#cost-analysis)
5. [Efficiency Problems](#efficiency-problems)
6. [Optimization Proposals](#optimization-proposals)
7. [Implementation Recommendations](#implementation-recommendations)

---

## Current Workflow Overview

The CXG annotation pipeline consists of three main steps:

```
1. prepare_data (Reference Retrieval)
   ├─ Load TSV annotations
   ├─ Group by dataset/article
   └─ Download publication full text

2. expand_full_names (Name Expansion)
   ├─ For each article's annotations
   ├─ Send full text + batch of 5 annotations to GPT-5
   └─ Extract expanded names and synonyms

3. ground_annotations (Ontology Mapping)
   └─ Map expanded names to Cell Ontology IDs
```

**Services Involved:**
- `DatasetLoader` - Loads TSV data
- `PublicationFetcher` - Downloads full text
- `ExpansionService` - Expands cell type names
- `GroundingService` - Maps to ontology

---

## Step 1: Reference Retrieval

### Overview

Downloads full text from academic publications given DOI identifiers.

**Location**: `src/amica/services/publication_fetcher.py`

### How It Works

```python
class PublicationFetcher:
    def ensure_text_assets(self, dois: Iterable[str]) -> set[str]:
        """Download publication full text for DOIs if not already cached."""
        for doi in dois:
            normalised = normalise_identifier(doi)
            file_path = self.layout.publications_dir / f"{normalised}.txt"

            if file_path.exists():  # ✅ Cache hit
                continue

            text = get_doi_text(doi)  # ⚠️ Complex fallback chain
            file_path.write_text(text, encoding="utf-8")
```

### Text Retrieval Strategy

The `get_doi_text()` function uses a **multi-tier fallback approach** (`src/amica/utils/pubmed_utils.py:66-99`):

```
Priority 1: DOI → PMID → Full Text (PubMed Central BioC XML)
    ↓ (if fails)
Priority 2: Crossref (preprint → published DOI) → PMID → Full Text
    ↓ (if fails)
Priority 3: Unpaywall full text retrieval
    ↓ (if fails)
Priority 4: Fall back to abstract only
```

#### Detailed Fallback Chain

1. **PubMed Central (PMC) Full Text via BioC XML**
   - Convert DOI → PMID using `doi_to_pmid()`
   - Fetch BioC XML from `https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmid}/ascii`
   - Extract text from `<passage><text>` tags
   - **Best case**: Full article text including methods, results, discussion

2. **Crossref Preprint Resolution**
   - Query Crossref API for `is-preprint-of` relation
   - Get published DOI → convert to PMID → fetch full text
   - **Use case**: bioRxiv/medRxiv preprints linked to journal publications

3. **Unpaywall Full Text**
   - Uses `DOIFetcher` (email: `ub2@sanger.ac.uk`)
   - Attempts to get open access full text PDF/HTML
   - **Coverage**: ~30M open access articles

4. **PubMed Abstract Only**
   - Fetch via `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`
   - Returns title + abstract only (no methods/results)
   - **Fallback**: Better than nothing for expansion context

### Caching Strategy

- **Storage**: `{layout.publications_dir}/{normalized_doi}.txt`
- **Check**: `if file_path.exists()` - simple filesystem check
- **Benefit**: Avoids redundant API calls across pipeline runs
- **Limitation**: No cache expiration or validation

### Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Cache Hit** | ~instant | Filesystem read |
| **PMC Full Text** | 2-5 seconds | XML parsing + network |
| **Crossref Lookup** | 1-2 seconds | JSON API |
| **Unpaywall** | 3-10 seconds | PDF download/conversion |
| **Abstract Only** | 1-2 seconds | Lightweight XML |

### Issues with Current Implementation

1. **Sequential Downloads**: No parallelization
2. **No Retry Logic**: Network errors cause silent failures
3. **No Rate Limiting**: Could hit NCBI E-utilities rate limits
4. **Text Quality Varies**: Abstract vs full text affects expansion quality
5. **Large File Storage**: Full texts can be 50-200KB each

---

## Step 2: Name Expansion

### Overview

Enriches short cell type labels (e.g., "NK cell") with full names, synonyms, and tissue context by reading the associated publication.

**Location**: `src/amica/services/expansion_service.py`

### How It Works

```python
class ExpansionService:
    async def expand_annotations(self, bundle: PreparedAnnotationBundle):
        # Group annotations by dataset → article
        for dataset_name in bundle.dataset_names:
            for article_id, annotations in dataset_articles:
                article_text = read_full_text(article_id)  # 📄 Full paper

                # Process in batches of 5
                for batch in chunks(annotations, batch_size=5):
                    if cache_exists(batch):
                        load_from_cache()
                    else:
                        result = await celltype_agent.run(
                            prompt=PROMPT_TEMPLATE.format(
                                cc_json=batch_labels,
                                paper_full_text=article_text  # ⚠️ LARGE
                            )
                        )
                        cache_result()
```

### Agent Configuration

**Model**: `openai:gpt-5` (GPT-5)
**Agent**: `paper_celltype/paper_celltype_agent.py`

```python
celltype_agent = Agent(
    model="openai:gpt-5",
    deps_type=PaperCTDependencies,
    output_type=BiocurationOutput,
    system_prompt=SYSTEM_PROMPT,
    defer_model_check=True,
)
```

### System Prompt

```
You are a Biocuration Assistant. Your primary task is to extract precise cell type
information from provided academic paper content, its supplementary materials and an
associated JSON file, and then format this information into a structured TSV-compatible
output.

IMPORTANT CONSTRAINTS:
- Do not use external knowledge. All information must be derived *only* from the
  provided paper and supplementary material content.
- Do not infer, invent, or hallucinate any information. If information is not explicitly
  found, leave the field blank.
- Strictly adhere to the output format (TSV-compatible list of dictionaries).
```

### User Prompt Template

```python
PROMPT_TEMPLATE = """
You are tasked with extracting cell type information from the provided academic paper
content, and the provided JSON data.

The JSON contains cell type annotations (cc.label column) from single-cell transcriptomic
data.

Based on the following JSON data and academic paper content, generate a list of structured
cell type entries. Each entry must follow the `CellTypeEntry` schema.

--- JSON List Input Data:
{cc_json}

--- Academic Paper Content (extracted from PDF):
{paper_full_text}

--- COLUMN DEFINITIONS AND LOGIC:
- `name`: The exact `cc.label` from the input JSON.
- `full_name`: Use the following logic:
    1. If the full label (e.g., "SI_TA") is defined directly in the paper, use the exact
       definition.
    2. If not, check if individual parts (e.g., prefixes, suffixes) are defined and
       reconstruct/assemble the `full_name` from the parts found.
    3. If the label begins with a defined prefix abbreviation, expand the prefix and append
       the remaining label.
    4. If only one part is defined, use just that part.
    5. If no parts are defined, leave this field blank.
- `paper_synonyms`: Use only synonyms mentioned in the paper via abbreviation lists or
  explicit synonym statements. Separate entries with semicolons (;).
- `tissue_context`: Exact quoted tissue(s) or anatomical terms from the paper where the
  cell type was identified.

Process all `cc.label` entries from the JSON data automatically.
Do not ask for confirmation.
Provide the output as a JSON array of `CellTypeEntry` objects.
"""
```

### Output Schema

```python
class CellTypeEntry(BaseModel):
    name: str  # Original cc.label
    full_name: str | None  # Expanded name from paper
    paper_synonyms: str | None  # Synonyms (semicolon-separated)
    tissue_context: str | None  # Tissue/anatomical context

class BiocurationOutput(BaseModel):
    cell_type_annotations: list[CellTypeEntry]
```

### Batch Processing

**Default batch size**: 5 annotations per API call
**Configurable via**: `CXG_ANNOTATIONS_BATCH_SIZE` environment variable

**Example batch input**:
```json
[
  {"cc.label": "NK cell"},
  {"cc.label": "CD4+ T cell"},
  {"cc.label": "B cell"},
  {"cc.label": "Monocyte"},
  {"cc.label": "Dendritic cell"}
]
```

**Example output**:
```json
{
  "cell_type_annotations": [
    {
      "name": "NK cell",
      "full_name": "natural killer cell",
      "paper_synonyms": "NK; natural killer lymphocyte",
      "tissue_context": "peripheral blood mononuclear cells (PBMCs)"
    },
    ...
  ]
}
```

### Caching Strategy

**Cache location**: `{layout.expansions_dir}/{dataset_name}/{article_slug}_batch_{N}.json`

**Cache validation**:
```python
cached_inputs = [entry.get("input_name") for entry in cached_payload]
expected_inputs = [record.annotation_text for record in batch]
if cached_inputs != expected_inputs:
    # Cache mismatch - regenerate
    cache_file.unlink()
```

Ensures cache is invalidated if annotation list changes.

### Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Batch Size** | 5 annotations | Configurable |
| **Prompt Size** | 50-200K tokens | Depends on paper length |
| **Model** | GPT-5 | Most expensive OpenAI model |
| **Latency** | 10-30 seconds | Per batch |
| **Cache Hit** | ~instant | JSON deserialization |

---

## Cost Analysis

### Token Usage Estimation

**Per batch API call:**

| Component | Tokens | Cost (GPT-5) |
|-----------|--------|--------------|
| System Prompt | ~200 | Negligible |
| User Prompt Template | ~350 | Negligible |
| **Full Paper Text** | **30,000-100,000** | **$3-$10** |
| Batch JSON (5 labels) | ~100 | Negligible |
| **Total Input** | **~30,650-100,650** | **$3.07-$10.07** |
| Output (5 entries) | ~500 | $0.15-$0.50 |
| **TOTAL PER BATCH** | **~31,150-101,150** | **$3.22-$10.57** |

*Note: GPT-5 pricing estimated at $10/1M input tokens, $30/1M output tokens*

### Example Pipeline Cost

**Scenario**: 1 dataset, 1 article, 100 annotations

- **Batches needed**: 100 / 5 = 20 batches
- **Full paper text**: Repeated 20 times in prompts
- **Estimated cost**: 20 × $5 (avg) = **$100 per article**

**Scenario**: 10 datasets, 50 articles total, 5,000 annotations

- **Articles**: 50
- **Avg batches per article**: 100 / 5 = 20
- **Total batches**: 50 × 20 = 1,000 batches
- **Estimated cost**: 1,000 × $5 = **$5,000 for expansion step alone**

### Cost Drivers

1. **Full paper text redundancy** (30-100K tokens × batches per article)
2. **GPT-5 pricing** (most expensive OpenAI model)
3. **Small batch size** (5 annotations = more API calls)
4. **No deduplication** (same cell type name expanded multiple times)

---

## Efficiency Problems

### Problem 1: Massive Token Redundancy

**Issue**: Full paper text (30-100K tokens) is included in **every batch** for the same article.

**Example**: Article with 100 annotations
- Batches: 100 / 5 = 20 batches
- Paper text sent: 20 times
- **Redundant tokens**: 19 × 50,000 = 950,000 tokens
- **Wasted cost**: ~$9.50 per article just on redundancy

**Why it happens**: Each batch is an independent API call with the full prompt.

### Problem 2: Expensive Model for Simple Task

**Issue**: Using GPT-5 (most expensive) for what is essentially a **named entity extraction** task.

**Observations**:
- Task: Find abbreviation definitions in text
- Required capability: Search + pattern matching
- Doesn't need: Advanced reasoning, creative generation

**Alternative models**:
- GPT-4o: ~10× cheaper, sufficient for extraction
- GPT-4o-mini: ~50× cheaper, adequate for simple expansions
- Claude Haiku: ~100× cheaper, fast extraction

### Problem 3: Small Batch Size

**Issue**: Processing only 5 annotations per API call.

**Impact**:
- More API calls = more overhead
- More redundant full text transmission
- Higher latency (serial processing)

**Why 5?**: Likely chosen to avoid context limits, but could be optimized.

### Problem 4: No Deduplication

**Issue**: Same cell type name (e.g., "T cell") expanded multiple times across batches/articles.

**Example**: "T cell" appears 500 times across 20 articles
- Current: Expanded 500 times (in various batches)
- Optimal: Expand once, reuse

**Caveat**: Paper-specific synonyms differ, but core expansion is often identical.

### Problem 5: Sequential Processing

**Issue**: Batches processed serially, not in parallel.

```python
for batch in chunks(annotations, 5):
    result = await self.agent.run(prompt)  # ⏳ Serial
```

**Lost opportunity**: Could run multiple batches concurrently.

### Problem 6: Inefficient Full Text Retrieval

**Issue**: No parallel downloads in `PublicationFetcher`.

```python
for doi in dois:
    text = get_doi_text(doi)  # ⏳ Serial, no retry
```

**Impact**:
- Slow startup for large datasets
- Network failures halt entire process

---

## Optimization Proposals

### 1. Eliminate Token Redundancy: Batch-All-At-Once Strategy

**Idea**: Send all annotations for an article in a **single API call** instead of multiple batches.

#### Implementation

```python
async def _expand_article_annotations(
    self,
    article_id: str,
    annotations: list[AnnotationRecord],
    article_text: str
):
    # OLD: Process in batches of 5
    # for batch in chunks(annotations, 5):
    #     result = await agent.run(prompt_with_full_text)

    # NEW: Process ALL at once
    all_labels = [{"cc.label": ann.annotation_text} for ann in annotations]
    prompt = PROMPT_TEMPLATE.format(
        cc_json=json.dumps(all_labels, indent=2),
        paper_full_text=article_text
    )
    result = await self.agent.run(prompt)
```

#### Benefits

- **Token reduction**: Full text sent once instead of N times
- **Cost savings**: ~90% reduction for articles with many annotations
- **Latency reduction**: 1 API call instead of 20

#### Risks

- **Context limits**: GPT-5 has 128K token limit
  - Full text: 50K tokens (avg)
  - 100 annotations: ~2K tokens
  - Total: ~52K tokens ✅ Well within limit
- **Output length**: GPT-5 can handle large outputs (tested to 16K+ tokens)

#### Validation Strategy

- If annotations exceed safe limit (~500 entries):
  - Fall back to larger batches (e.g., 50 instead of 5)
  - Implement chunking with overlap warnings

### 2. Model Downgrade: Use GPT-4o or GPT-4o-mini

**Idea**: Switch from GPT-5 to a cheaper model for extraction tasks.

#### Proposed Tiers

| Model | Cost/1M tokens (input) | Use Case |
|-------|------------------------|----------|
| **GPT-5** | $10.00 | Complex reasoning (keep for grounding?) |
| **GPT-4o** | $1.00-$2.50 | Standard extraction (recommended) |
| **GPT-4o-mini** | $0.15-$0.30 | Simple expansion (test) |
| **Claude Haiku** | $0.25 | Fast batch extraction (test) |

#### Implementation

```python
celltype_agent = Agent(
    model="openai:gpt-4o",  # Changed from gpt-5
    deps_type=PaperCTDependencies,
    output_type=BiocurationOutput,
    system_prompt=SYSTEM_PROMPT,
    defer_model_check=True,
)
```

#### Benefits

- **Cost reduction**: 5-10× cheaper per API call
- **Speed**: GPT-4o often faster than GPT-5
- **Quality**: Likely sufficient for named entity extraction

#### Validation

- Run A/B test on 100 annotations:
  - GPT-5 vs GPT-4o expansion quality
  - Compare `full_name` accuracy, synonym completeness
  - Measure downstream grounding success rate

### 3. Increase Batch Size

**Idea**: Process 20-50 annotations per batch instead of 5.

#### Rationale

If we're not eliminating batches entirely (Proposal #1), at least make them larger:
- Fewer API calls
- Better amortization of prompt overhead
- Still manageable output size

#### Implementation

```python
class CxgPipelineSettings:
    annotations_batch_size: int = 50  # Changed from 5
```

Or expose per-step batch sizes:
```python
class CxgPipelineSettings:
    expansion_batch_size: int = 50
    grounding_batch_size: int = 5  # Keep smaller for tool call overhead
```

#### Benefits

- **Cost reduction**: ~70% fewer API calls (if 25 instead of 5)
- **Token efficiency**: Prompt overhead amortized over more annotations

### 4. Deduplication Layer

**Idea**: Cache expansions by `cc.label` globally, not just per-article-batch.

#### Implementation

```python
class ExpansionService:
    def __init__(self, ...):
        self.global_expansion_cache: dict[str, CellTypeEntry] = {}
        self._load_global_cache()

    async def _expand_article_annotations(self, ...):
        # Filter out already-expanded labels
        uncached = [ann for ann in annotations
                    if ann.annotation_text not in self.global_expansion_cache]

        if uncached:
            result = await self.agent.run(uncached)
            for entry in result:
                self.global_expansion_cache[entry.name] = entry

        # Apply cached + new
        for ann in annotations:
            ann.enrichment = self.global_expansion_cache[ann.annotation_text]
```

#### Benefits

- **Deduplication**: "T cell" expanded once, reused 500 times
- **Cost savings**: ~60-80% for datasets with common cell types

#### Risks

- **Context loss**: Paper-specific synonyms might be missed
- **Tissue context**: Will be generic, not article-specific

#### Hybrid Approach

1. First pass: Expand unique labels globally (no paper context)
2. Second pass: Re-expand labels that appear in multiple articles with paper context
3. Merge: Use paper-specific if available, else fall back to global

### 5. Parallel Processing

**Idea**: Process batches concurrently using `asyncio.gather()`.

#### Implementation

```python
async def expand_annotations(self, bundle: PreparedAnnotationBundle):
    tasks = []
    for dataset_name in bundle.dataset_names:
        for article_id, annotations in dataset_articles:
            task = self._expand_article_annotations(
                dataset_name, article_id, annotations, cache_dir
            )
            tasks.append(task)

    # Run all articles in parallel
    await asyncio.gather(*tasks)
```

Or within an article:
```python
async def _expand_article_annotations(self, ...):
    batch_tasks = [
        self._generate_and_cache_expansions(batch, article_text, cache_file)
        for batch in chunks(annotations, batch_size)
    ]
    await asyncio.gather(*batch_tasks)
```

#### Benefits

- **Latency reduction**: 5-10× faster for large datasets
- **Throughput**: Maximize API concurrency

#### Risks

- **Rate limits**: OpenAI has per-minute token limits
- **Memory**: All prompts in memory simultaneously

#### Mitigation

- Use `asyncio.Semaphore(max_concurrent=10)` to limit concurrency
- Implement exponential backoff for rate limit errors

### 6. Smarter Reference Retrieval

**Idea**: Parallelize publication downloads, add retry logic.

#### Implementation

```python
class PublicationFetcher:
    async def ensure_text_assets(self, dois: Iterable[str]) -> set[str]:
        tasks = [self._fetch_with_retry(doi) for doi in dois]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {doi for doi, success in results if success}

    async def _fetch_with_retry(self, doi: str, max_retries=3) -> tuple[str, bool]:
        for attempt in range(max_retries):
            try:
                text = await asyncio.to_thread(get_doi_text, doi)
                if text:
                    return (doi, True)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error("Failed to fetch %s after %d attempts", doi, max_retries)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return (doi, False)
```

#### Benefits

- **Speed**: Download 10-20 papers concurrently
- **Reliability**: Retry on transient failures
- **User experience**: Progress bar, better error messages

### 7. Prompt Compression

**Idea**: Use extractive summarization to reduce paper text size.

#### Strategy

Before sending full paper text:
1. Extract sections mentioning cell types
2. Include: abstract, methods (cell type definitions), results (cell populations)
3. Exclude: introduction (background), references, acknowledgments

#### Implementation

```python
def extract_relevant_sections(full_text: str) -> str:
    """Extract cell-type-relevant sections from paper."""
    sections = parse_sections(full_text)

    relevant = []
    if "abstract" in sections:
        relevant.append(sections["abstract"])
    if "methods" in sections:
        relevant.append(sections["methods"])
    if "results" in sections:
        relevant.append(sections["results"])

    # Also extract paragraphs mentioning cell type keywords
    keywords = ["cell type", "cluster", "population", "marker", "CD", "lineage"]
    relevant_paragraphs = [
        para for para in sections.get("discussion", "").split("\n\n")
        if any(kw in para.lower() for kw in keywords)
    ]
    relevant.extend(relevant_paragraphs)

    return "\n\n".join(relevant)
```

#### Benefits

- **Token reduction**: 50-70% smaller prompts
- **Focus**: Removes irrelevant content
- **Quality**: Might improve by reducing noise

#### Risks

- **Information loss**: Cell type definitions in unexpected sections
- **Parsing errors**: Section detection is brittle

#### Validation

- A/B test: Full text vs compressed text
- Measure: Expansion completeness, grounding success

---

## Implementation Recommendations

### Phase 1: Quick Wins (Immediate - Low Risk)

**1. Increase Batch Size** (1 hour)
- Change `annotations_batch_size` from 5 to 25-50
- Test on single dataset
- **Expected savings**: 60-70% fewer API calls

**2. Parallel Publication Fetching** (2 hours)
- Add `asyncio.gather()` to `PublicationFetcher`
- Add retry logic with exponential backoff
- **Expected improvement**: 5-10× faster downloads

**3. Parallel Batch Processing** (2 hours)
- Add `asyncio.gather()` for batches within an article
- Use `Semaphore(10)` to limit concurrency
- **Expected improvement**: 3-5× faster expansion

**Total Phase 1 effort**: 5 hours
**Expected cost reduction**: ~50-60%
**Expected speed improvement**: 5-10×

### Phase 2: Major Optimizations (Week 1-2 - Medium Risk)

**4. Model Downgrade to GPT-4o** (1 day)
- Change model from `gpt-5` to `gpt-4o`
- Run validation tests on 100-500 annotations
- Compare expansion quality and grounding accuracy
- **Expected savings**: 80-90% cost reduction (if quality acceptable)

**5. Batch-All-At-Once Strategy** (2 days)
- Implement single API call per article
- Add context limit detection and fallback
- Update caching to handle article-level results
- **Expected savings**: 90-95% token reduction on full text

**6. Global Deduplication Cache** (2 days)
- Implement cross-article label cache
- Add hybrid global+paper-specific expansion
- Persist cache across pipeline runs
- **Expected savings**: 60-80% for common labels

**Total Phase 2 effort**: 5 days
**Expected cost reduction**: ~95% (combined with Phase 1)
**Expected speed improvement**: 10-20×

### Phase 3: Advanced Optimizations (Week 3-4 - Higher Risk)

**7. Prompt Compression** (3 days)
- Implement section extraction
- Test on diverse paper formats
- Validate expansion quality
- **Expected savings**: 50-70% additional token reduction

**8. Alternative Models** (3 days)
- Test GPT-4o-mini, Claude Haiku, Claude Sonnet
- Benchmark quality vs cost tradeoffs
- Implement model selection strategy
- **Expected savings**: 90-95% if mini models acceptable

**Total Phase 3 effort**: 6 days
**Expected cost reduction**: ~98% (if aggressive choices work)

---

## Summary: Expected Impact

### Current State (Baseline)

| Metric | Value |
|--------|-------|
| **Model** | GPT-5 |
| **Batch size** | 5 annotations |
| **Token redundancy** | 95% (full text repeated) |
| **Parallelization** | None (serial) |
| **Cost per article** | ~$100 (100 annotations) |
| **Cost per dataset** | ~$5,000 (50 articles) |

### After Phase 1 (Quick Wins)

| Metric | Value | Improvement |
|--------|-------|-------------|
| **Batch size** | 25 annotations | 5× |
| **Parallelization** | 10× concurrent | 10× faster |
| **Cost per article** | ~$50 | **50% reduction** |
| **Cost per dataset** | ~$2,500 | **50% reduction** |

### After Phase 2 (Major Optimizations)

| Metric | Value | Improvement |
|--------|-------|-------------|
| **Model** | GPT-4o | 5× cheaper |
| **Token redundancy** | 5% (single call) | 20× reduction |
| **Deduplication** | 70% cache hit | 3× fewer expansions |
| **Cost per article** | ~$2 | **98% reduction** |
| **Cost per dataset** | ~$100 | **98% reduction** |

### After Phase 3 (Aggressive)

| Metric | Value | Improvement |
|--------|-------|-------------|
| **Model** | GPT-4o-mini | 50× cheaper |
| **Prompt size** | 50% compressed | 2× reduction |
| **Cost per article** | ~$0.50 | **99.5% reduction** |
| **Cost per dataset** | ~$25 | **99.5% reduction** |

---

## Risks and Mitigations

### Risk 1: Quality Degradation

**Risk**: Cheaper models or compressed prompts produce worse expansions.

**Mitigation**:
- Implement A/B testing framework
- Define quality metrics (expansion completeness, grounding success rate)
- Only proceed if quality ≥95% of baseline
- Keep GPT-5 as fallback for difficult cases

### Risk 2: Context Limit Violations

**Risk**: Large articles + many annotations exceed model context limits.

**Mitigation**:
- Implement token counting before API call
- Fall back to batching if total exceeds 100K tokens
- Add warnings in logs for oversized inputs

### Risk 3: Rate Limiting

**Risk**: Parallel processing hits OpenAI rate limits.

**Mitigation**:
- Use `asyncio.Semaphore` to limit concurrency
- Implement exponential backoff with retry
- Monitor rate limit headers, adjust dynamically

### Risk 4: Cache Invalidation

**Risk**: Global deduplication cache becomes stale or incorrect.

**Mitigation**:
- Version cache files with pipeline version
- Invalidate cache on prompt/model changes
- Allow manual cache clearing
- Store metadata (timestamp, model, prompt hash)

---

## Conclusion

The current reference retrieval and name expansion steps have significant inefficiencies:

1. **Massive token redundancy** from repeating full text
2. **Expensive model** (GPT-5) for simple extraction
3. **Small batches** causing excessive API calls
4. **No parallelization** slowing pipeline
5. **No deduplication** re-expanding common labels

**Recommended approach**: Implement in phases
- **Phase 1** (5 hours): Quick wins for immediate 50% cost reduction
- **Phase 2** (1-2 weeks): Major optimizations for 98% cost reduction
- **Phase 3** (optional): Aggressive compression for 99%+ reduction

**Best ROI**: Phase 1 + Phase 2 provides 98% cost reduction with low risk and reasonable effort.

**Critical validation**: Always A/B test quality before deploying cheaper/faster approaches to production.
