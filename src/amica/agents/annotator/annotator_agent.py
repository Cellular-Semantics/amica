"""
Ontology based Annotator Agent.
"""

import logging
from typing import List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent

cell_logger = logging.getLogger(__name__)
cell_logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
cell_logger.addHandler(console)

cell_logger.propagate = False

from amica.utils.cell_tools import search_cl
from .annotator_config import AnnotatorDependencies

ANNOTATOR_SYSTEM_PROMPT_NEW = """
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
        If the input is a generic term, such as a base cell-type concept with no qualifiers (e.g., “myeloid progenitor”) or a single, broad adjective describing a tissue (e.g., “neural”), you must prefer the broader, canonical CL term. For an adjectival input, this is typically the '[adjective] cell' term or its direct synonym (e.g., 'neuron').
        * **Rule 4: Penalize Over-Specific Qualifiers.**
        Down-rank candidate terms that include qualifiers absent from the input, such as lineage restrictions (“lineage restricted”), activation states (“activated”), species (“human”), or protein markers (“CD4-positive”). Only select terms with these qualifiers if the input explicitly justifies that level of specificity.
        
    5.  **Assemble and Return TextAnnotationResult:**
        * After processing all text spans (`name`, `full_name`) for a single input JSON object and collecting all resulting `TextAnnotation` objects into `current_annotations`, order current_annotations so that any annotation derived from full_name appears first (if it exists).
        * Create a single `TextAnnotationResult` object and set the `annotations` field to this ordered `current_annotations` list.
        * Return this single `TextAnnotationResult` object for the current input JSON object.

    You can use different functions to support curators in their tasks:
    - `search_cl` Search the Cell Ontology for a term.
"""

ANNOTATOR_SYSTEM_PROMPT = """
    Your primary goal is to map text from the "name", "full_name" fields of each JSON object to terms from the cell ontology.

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

    4.  **Assemble and Return TextAnnotationResult:**
        * After processing all text spans (`name`, `full_name`) for a single input JSON object and collecting all resulting `TextAnnotation` objects into `current_annotations`, create a single `TextAnnotationResult` object.
        * Set the `annotations` field of this `TextAnnotationResult` to the `current_annotations` list.
        * Return this single `TextAnnotationResult` object for the current input JSON object.

    You can use different functions to support curators in their tasks:
    - `search_cl` Search the Cell Ontology for a term.
"""


class TextAnnotation(BaseModel):
    """
    A text annotation is a span of text and the cl ID and label for the cell type it mentions.
    Use `text` for the source text, and `cl_id` and `cl_label` for the cl ID and label of the cell type in the ontology.
    """

    input_name: str
    text: str
    cl_id: Optional[str] = None
    cl_label: Optional[str] = None


class TextAnnotationResult(BaseModel):
    annotations: List[TextAnnotation]


annotator_agent = Agent(
    model="openai:gpt-5",
    # model="openai:gpt-4.1",
    # model="openai:gpt-4o",
    # model="openai:gpt-4o-2024-11-20",
    deps_type=AnnotatorDependencies,
    result_type=TextAnnotationResult,
    system_prompt=ANNOTATOR_SYSTEM_PROMPT_NEW,
    defer_model_check=True,
)

annotator_agent.tool(search_cl)
