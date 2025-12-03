# Annotator Agent Prompt Structure

**Date**: 2025-12-03
**Purpose**: Complete documentation of the prompts, tools, and output formats used by the ontology annotator agent

---

## Table of Contents

1. [Overview](#overview)
2. [System Prompt](#system-prompt)
3. [Tool Definitions](#tool-definitions)
4. [User Prompt Format](#user-prompt-format)
5. [Output Format Specification](#output-format-specification)
6. [How Output is Enforced](#how-output-is-enforced)
7. [Agent Configuration](#agent-configuration)
8. [Complete Flow](#complete-flow)

---

## Overview

The annotator agent is responsible for mapping cell type text from dataset annotations to terms in the Cell Ontology (CL). It uses the pydantic-ai framework with structured outputs to ensure reliable, schema-compliant responses.

**Location**: `src/amica/agents/annotator/annotator_agent.py`

**Primary Purpose**: Map text from `name`, `full_name`, and `paper_synonyms` fields to Cell Ontology (CL) IDs and labels.

---

## System Prompt

The agent uses `ANNOTATOR_SYSTEM_PROMPT_NEW` as its system prompt (defined in `src/amica/agents/annotator/annotator_agent.py:24-76`):

```
Your primary goal is to map text from the "name", "full_name", "paper_synonyms" fields of each JSON object to terms from the cell ontology.

For each individual JSON object in the input array, you **must** produce exactly one `TextAnnotationResult` object. This single `TextAnnotationResult` object will contain all `TextAnnotation` instances derived from that input JSON object's relevant fields.

Here's how to process each JSON object and construct its corresponding `TextAnnotationResult`:

1.  **Initialize Annotation Collection:**
    * For each input JSON object, create an empty list to collect `TextAnnotation` objects. Let's call it `current_annotations`.

2.  **Identify and Process Text Spans for Search:**
    * **For the "name" field:**
        * Use the entire "name" value as a text span.
        * Process it to create a `TextAnnotation` (following steps below).
        * Add the created `TextAnnotation` to `current_annotations`.
    * **For the "full_name" field:**
        * Use the entire "full_name" value as a text span.
        * Process it to create a `TextAnnotation`.
        * Add the created `TextAnnotation` to `current_annotations`.

3.  **Details for Processing Each Text Span to Create a TextAnnotation:**
    * **Convert to Singular:** Before searching, convert all plural forms of cell types within the text span to their singular form.
    * **Search for CL ID:** Use the `search_cl` tool to find a corresponding cell ontology (CL) ID and its associated label for the given text span.
        * **Prioritize a direct match.**
        * **If no direct match is found, be sure to try different combinations of synonyms.** This includes:
            * Substituting terms in the span with common synonyms of those terms.
            * Converting between the forms 'X Y' and 'Y of X' where X is a tissue or anatomical structure (potentially inferred from "tissue_context" of the input Json object or common knowledge) and Y is a cell type.
    * **Construct TextAnnotation:** Create a `TextAnnotation` object with the following:
        * `input_name`: The value from the "name" field of the original input JSON object.
        * `text`: The exact text span that was used for the CL search (after pluralization conversion, but before any synonym substitutions used by the `search_cl` tool).
        * `cl_id`: The found CL ID. If no CL ID can be found after exhaustive searching using all strategies, set this field to "NO MATCH found".
        * `cl_label`: The corresponding CL label if a `cl_id` was found. If `cl_id` is "NO MATCH found", this can be `None`.

4.  **Post-Search Filtering and Selection Logic:**
    After `search_cl` returns a list of potential matches, you **must** apply the following rules in order:

    * **Rule 1: Prioritize CL Ontology.**
      Your primary goal is to return a Cell Ontology (CL) ID. Even if another ontology provides an exact string match (e.g., UBERON for anatomy) and the CL result is only a partial match, you **must** prefer the CL term.
    * **Rule 2: Apply the "Derived From" Heuristic.**
      If the input describes an anatomical structure (e.g., Medial Ganglionic Eminence) and a candidate CL term is a cell type explicitly described as being derived from that structure (e.g., medial ganglionic eminence derived interneuron), you **must** treat it as a strong and valid match. Do not discard it simply because of additional descriptive words. Only apply this heuristic if the derived cell type is biologically relevant to the query.
    * **Rule 3: Prefer Broader Canonical Terms for Generic Inputs.**
    If the input is a generic term, such as a base cell-type concept with no qualifiers (e.g., "myeloid progenitor") or a single, broad adjective describing a tissue (e.g., "neural"), you must prefer the broader, canonical CL term. For an adjectival input, this is typically the '[adjective] cell' term or its direct synonym (e.g., 'neuron').
    * **Rule 4: Penalize Over-Specific Qualifiers.**
    Down-rank candidate terms that include qualifiers absent from the input, such as lineage restrictions ("lineage restricted"), activation states ("activated"), species ("human"), or protein markers ("CD4-positive"). Only select terms with these qualifiers if the input explicitly justifies that level of specificity.

5.  **Assemble and Return TextAnnotationResult:**
    * After processing all text spans (`name`, `full_name`) for a single input JSON object and collecting all resulting `TextAnnotation` objects into `current_annotations`, order current_annotations so that any annotation derived from full_name appears first (if it exists).
    * Create a single `TextAnnotationResult` object and set the `annotations` field to this ordered `current_annotations` list.
    * Return this single `TextAnnotationResult` object for the current input JSON object.

You can use different functions to support curators in their tasks:
- `search_cl` Search the Cell Ontology for a term.
```

### Key Instructions in System Prompt

1. **Pluralization handling**: Convert plurals to singular before searching
2. **Synonym exploration**: Try multiple synonym combinations if no direct match
3. **Form conversion**: Try both "X Y" and "Y of X" patterns
4. **Filtering rules**: Four-tier decision logic for selecting best match
5. **Ordering**: Annotations from `full_name` should appear first

---

## Tool Definitions

The agent has access to one tool: `search_cl`

**Location**: `src/amica/agents/annotator/annotator_tools.py:14-33`

### Tool: `search_cl`

```python
def search_cl(ctx: RunContext[str], term: str) -> List[Tuple[str, str]]:
    """
    Search the Cell Ontology for a term and return CL identifier/label pairs.

    Note that search should take into account synonyms, but synonyms may be incomplete,
    so if you cannot find a concept of interest, try searching using related or synonymous
    terms.

    Args:
        ctx: The run context (unused, but required by the tool signature)
        term: The term to search for.

    Returns:
        A list of tuples, each containing a CL ID and a label.
    """
    adapter = get_adapter("ols:cl")
    results = adapter.basic_search(term)
    labels = list(adapter.labels(results))
    logger.debug("CL search query='%s' results=%s", term, labels)
    return labels
```

### How the Tool is Presented to the LLM

The tool is sent as a structured function definition in the API call:

```json
{
  "name": "search_cl",
  "description": "Search the Cell Ontology for a term and return CL identifier/label pairs.\n\nNote that search should take into account synonyms, but synonyms may be incomplete,\nso if you cannot find a concept of interest, try searching using related or synonymous\nterms.\n\nArgs:\n    ctx: The run context (unused, but required by the tool signature)\n    term: The term to search for.\n\nReturns:\n    A list of tuples, each containing a CL ID and a label.",
  "parameters": {
    "type": "object",
    "properties": {
      "term": {
        "type": "string",
        "description": "The term to search for."
      }
    },
    "required": ["term"]
  }
}
```

**Implementation**: Uses OLS (Ontology Lookup Service) adapter to search the Cell Ontology

---

## User Prompt Format

The actual user message sent to the agent is a JSON string containing enriched cell type entries.

**Source**: `src/amica/services/grounding_service.py:139-147`

### Format

```json
[
  {
    "name": "neural cell",
    "full_name": "neural progenitor cell",
    "paper_synonyms": "NPC, neural stem cell",
    "tissue_context": ""
  },
  {
    "name": "T cell",
    "full_name": "T lymphocyte",
    "paper_synonyms": "T-cell, thymocyte",
    "tissue_context": ""
  }
]
```

### Field Descriptions

- **`name`**: The original cell type annotation text from the dataset
- **`full_name`**: Expanded/enriched full name (generated by upstream expansion service)
- **`paper_synonyms`**: Synonyms extracted from the associated publication
- **`tissue_context`**: Tissue context information (currently always empty string)

### How It's Generated

```python
async def _run_grounding_agent(
    self, dataset_name: str, batch: Sequence[AnnotationRecord]
) -> List[TextAnnotation]:
    logger.info(
        "[%s] Grounding batch of %s annotations",
        dataset_name,
        len(batch),
    )
    expansions_json = json.dumps(
        [
            record.enrichment.model_dump()
            if isinstance(record.enrichment, CellTypeEntry)
            else record.enrichment
            for record in batch
        ],
        indent=2,
    )
    response: TextAnnotationResult = await self.agent.run(expansions_json)
    return response.output.annotations
```

---

## Output Format Specification

The agent must return structured data matching Pydantic models.

**Location**: `src/amica/agents/annotator/annotator_agent.py:121-134`

### Models

```python
class TextAnnotation(BaseModel):
    """
    A text annotation is a span of text and the cl ID and label for the cell type it mentions.
    Use `text` for the source text, and `cl_id` and `cl_label` for the cl ID and label
    of the cell type in the ontology.
    """
    input_name: str
    text: str
    cl_id: Optional[str] = None
    cl_label: Optional[str] = None


class TextAnnotationResult(BaseModel):
    annotations: List[TextAnnotation]
```

### Example Output

```json
{
  "annotations": [
    {
      "input_name": "neural cell",
      "text": "neural progenitor cell",
      "cl_id": "CL:0000743",
      "cl_label": "neural progenitor cell"
    },
    {
      "input_name": "neural cell",
      "text": "neural cell",
      "cl_id": "CL:0000540",
      "cl_label": "neuron"
    }
  ]
}
```

### Field Meanings

- **`input_name`**: Original `name` field from input JSON (for tracking)
- **`text`**: The text span that was searched (from `name` or `full_name`)
- **`cl_id`**: Cell Ontology ID (e.g., "CL:0000540") or "NO MATCH found"
- **`cl_label`**: Human-readable label from Cell Ontology

---

## How Output is Enforced

The output format is enforced through multiple mechanisms:

### 1. Pydantic Model Definition

The models define the schema with type hints and optional fields:

```python
class TextAnnotation(BaseModel):
    input_name: str              # Required
    text: str                    # Required
    cl_id: Optional[str] = None  # Optional
    cl_label: Optional[str] = None  # Optional
```

### 2. Agent Configuration

```python
annotator_agent = Agent(
    model="openai:gpt-5",
    deps_type=AnnotatorDependencies,
    output_type=TextAnnotationResult,  # ← This enforces the structure
    system_prompt=ANNOTATOR_SYSTEM_PROMPT_NEW,
    defer_model_check=True,
)
```

### 3. JSON Schema Generation

Pydantic-AI converts the models to JSON Schema and sends it to the LLM:

```json
{
  "name": "TextAnnotationResult",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "annotations": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "input_name": {"type": "string"},
            "text": {"type": "string"},
            "cl_id": {"type": ["string", "null"]},
            "cl_label": {"type": ["string", "null"]}
          },
          "required": ["input_name", "text"],
          "additionalProperties": false
        }
      }
    },
    "required": ["annotations"],
    "additionalProperties": false
  }
}
```

### 4. OpenAI Structured Outputs API

For OpenAI models (gpt-5, gpt-4o, etc.), pydantic-ai uses [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs), which:

- **Guarantees** the model returns valid JSON matching the schema
- **API-level enforcement** - the model cannot deviate from the schema
- **100% reliability** - no need for retry logic or validation fixes

### 5. Pydantic Validation

After receiving the response, pydantic validates it:

```python
response: TextAnnotationResult = await self.agent.run(expansions_json)
# response.output is a validated TextAnnotationResult instance
return response.output.annotations
```

If the response doesn't match the schema, `ValidationError` is raised.

### 6. System Prompt Reinforcement

The system prompt describes the expected format in natural language:

```
For each individual JSON object in the input array, you **must** produce
exactly one `TextAnnotationResult` object...
```

### Enforcement Summary

| Mechanism | Type | Purpose |
|-----------|------|---------|
| Pydantic Models | Schema Definition | Define data structure and types |
| `output_type` Parameter | Configuration | Tell pydantic-ai what to enforce |
| JSON Schema | API Parameter | Formal schema sent to LLM |
| Structured Outputs API | Hard Constraint | LLM physically cannot return invalid JSON |
| Pydantic Validation | Runtime Check | Ensure type safety in Python code |
| System Prompt | Soft Guidance | Explain semantic meaning to LLM |

---

## Agent Configuration

**Location**: `src/amica/agents/annotator/annotator_agent.py:137-148`

```python
annotator_agent = Agent(
    model="openai:gpt-5",
    # Alternative models (commented out):
    # model="openai:gpt-4.1",
    # model="openai:gpt-4o",
    # model="openai:gpt-4o-2024-11-20",
    deps_type=AnnotatorDependencies,
    output_type=TextAnnotationResult,
    system_prompt=ANNOTATOR_SYSTEM_PROMPT_NEW,
    defer_model_check=True,
)

# Register the search tool
annotator_agent.tool(search_cl)
```

### Configuration Parameters

- **`model`**: Currently using `openai:gpt-5` (GPT-5)
- **`deps_type`**: `AnnotatorDependencies` (for context/state management)
- **`output_type`**: `TextAnnotationResult` (enforces structured output)
- **`system_prompt`**: The large complex prompt (see above)
- **`defer_model_check`**: `True` (allows using models not yet in registry)

---

## Complete Flow

### Step-by-Step Execution

1. **Input Preparation** (`grounding_service.py`)
   - Load batch of `AnnotationRecord` objects
   - Convert enrichments to JSON array
   - Each record has `name`, `full_name`, `paper_synonyms`, `tissue_context`

2. **Agent Invocation**
   ```python
   response: TextAnnotationResult = await self.agent.run(expansions_json)
   ```

3. **What the LLM Receives**
   - **System Prompt**: Full `ANNOTATOR_SYSTEM_PROMPT_NEW` text
   - **Tool Definitions**: `search_cl` function schema with docstring
   - **User Message**: JSON array of cell type entries
   - **Output Schema**: JSON schema for `TextAnnotationResult`

4. **LLM Processing**
   - For each input JSON object:
     - Extract `name` and `full_name` fields
     - Convert plurals to singular
     - Call `search_cl` tool for each text span
     - Try synonym variations if no match
     - Apply filtering rules (4 rules from system prompt)
     - Create `TextAnnotation` objects
     - Assemble into `TextAnnotationResult`

5. **Tool Execution** (when LLM calls `search_cl`)
   ```python
   # LLM calls: search_cl(term="neural cell")
   adapter = get_adapter("ols:cl")
   results = adapter.basic_search("neural cell")
   labels = list(adapter.labels(results))
   # Returns: [("CL:0000540", "neuron"), ("CL:0000743", "neural progenitor cell"), ...]
   ```

6. **Response Validation**
   - OpenAI API ensures JSON matches schema
   - Pydantic validates and constructs `TextAnnotationResult` object
   - Python code receives type-safe Pydantic model

7. **Result Processing**
   ```python
   batch_groundings = response.output.annotations  # List[TextAnnotation]
   # Apply groundings to original AnnotationRecord objects
   # Cache results to disk
   # Continue to next batch
   ```

### Data Flow Diagram

```
Input Annotations (TSV)
    ↓
AnnotationRecord objects
    ↓
JSON serialization
    ↓
[System Prompt + Tools + User Message + Output Schema]
    ↓
LLM (GPT-5) with Structured Outputs
    ↓
← Tool calls → search_cl(term) → OLS API
    ↓
Validated TextAnnotationResult
    ↓
List[TextAnnotation]
    ↓
Applied to AnnotationRecord.grounding_cl_id
    ↓
Output TSV files
```

---

## Example Conversation Flow

### Input Message (User)
```json
[{
  "name": "neural cell",
  "full_name": "neural progenitor cell",
  "paper_synonyms": "",
  "tissue_context": ""
}]
```

### LLM Response (Tool Call)
```json
{
  "tool_calls": [
    {
      "function": "search_cl",
      "arguments": {"term": "neural progenitor cell"}
    }
  ]
}
```

### Tool Result
```python
[
  ("CL:0000743", "neural progenitor cell"),
  ("CL:0000047", "neuronal stem cell"),
  ("CL:0002319", "neural cell")
]
```

### LLM Response (Tool Call 2)
```json
{
  "tool_calls": [
    {
      "function": "search_cl",
      "arguments": {"term": "neural cell"}
    }
  ]
}
```

### Tool Result 2
```python
[
  ("CL:0002319", "neural cell"),
  ("CL:0000540", "neuron"),
  ("CL:0000125", "glial cell")
]
```

### Final LLM Response (Structured Output)
```json
{
  "annotations": [
    {
      "input_name": "neural cell",
      "text": "neural progenitor cell",
      "cl_id": "CL:0000743",
      "cl_label": "neural progenitor cell"
    },
    {
      "input_name": "neural cell",
      "text": "neural cell",
      "cl_id": "CL:0002319",
      "cl_label": "neural cell"
    }
  ]
}
```

---

## Notes and Observations

### Strengths

1. **Double enforcement**: Structured Outputs API + Pydantic validation ensures reliability
2. **Clear instructions**: Detailed system prompt with examples and rules
3. **Flexible matching**: Multiple synonym strategies and form conversions
4. **Caching**: Results cached to disk to avoid redundant API calls
5. **Batch processing**: Efficient handling of large annotation sets

### Potential Issues

1. **Prompt length**: Very long system prompt (may hit context limits)
2. **Tool call volume**: Multiple `search_cl` calls per annotation (API costs)
3. **Filtering complexity**: Four-tier filtering rules rely on LLM judgment
4. **Plural conversion**: LLM must handle pluralization manually (no external tool)

### Recent Changes

- System prompt switched from `ANNOTATOR_SYSTEM_PROMPT` to `ANNOTATOR_SYSTEM_PROMPT_NEW`
- New version adds 4 post-search filtering rules
- Emphasis on ordering: `full_name` annotations should appear first

---

## References

- **Agent Definition**: `src/amica/agents/annotator/annotator_agent.py`
- **Tool Implementation**: `src/amica/agents/annotator/annotator_tools.py`
- **Service Integration**: `src/amica/services/grounding_service.py`
- **Workflow Graph**: `src/amica/graphs/cxg_annotate.py`
- **Pydantic-AI Docs**: https://ai.pydantic.dev/
- **OpenAI Structured Outputs**: https://platform.openai.com/docs/guides/structured-outputs
