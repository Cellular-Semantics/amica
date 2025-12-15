"""
Agent for Cell Ontology.
"""

import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from .paper_celltype_config import PaperCTDependencies
from .paper_celltype_tools import search_cached_snippets

cell_logger = logging.getLogger(__name__)
cell_logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console.setFormatter(formatter)
cell_logger.addHandler(console)

cell_logger.propagate = False

SYSTEM_PROMPT = """
    You are a Biocuration Assistant. Your primary task is to extract precise cell type information
    from provided academic paper content, its supplementary materials and an associated JSON file, 
    and then format this information into a structured TSV-compatible output.

    Your core objective is to process each 'cc.label' from the JSON file according to the
    detailed instructions provided in the task prompt.

    IMPORTANT CONSTRAINTS:
    - Do not use external knowledge. All information must be derived *only* from the provided paper 
    and supplementary material content.
    - Do not infer, invent, or hallucinate any information. If information is not explicitly found, 
    leave the field blank.
    - Strictly adhere to the output format (TSV-compatible list of dictionaries).
    - Use the provided tools to read the JSON and PDF data.
"""


class CellTypeEntry(BaseModel):
    name: str = Field(..., description="The exact cc.label from the input JSON.")
    full_name: str | None = Field(
        None,
        description="The expanded or reconstructed full name of the cell type as defined in the paper.",
    )
    paper_synonyms: str | None = Field(
        None, description="Synonyms mentioned in the paper, separated by semicolons."
    )
    tissue_context: str | None = Field(
        None,
        description="Exact quoted tissue(s) or anatomical terms from the paper where the cell type was identified.",
    )


class BiocurationOutput(BaseModel):
    cell_type_annotations: list[CellTypeEntry] = Field(
        ..., description="A list of extracted cell type annotations."
    )


celltype_agent = Agent(
    model="openai:gpt-5",
    # model="openai:gpt-4.1",
    # model="openai:gpt-4o-2024-11-20",
    deps_type=PaperCTDependencies,
    output_type=BiocurationOutput,
    system_prompt=SYSTEM_PROMPT,
    defer_model_check=True,
)

# celltype_agent.tool(get_full_text)
# celltype_agent.tool(read_json)
celltype_agent.tool(search_cached_snippets)
