"""
Gradio interface for the PaperQA agent.
"""
import os
import logging
from typing import List, Optional, Any

import gradio as gr

from aurelian.utils.async_utils import run_sync
from .paper_celltype_agent import celltype_agent
from .paper_celltype_config import PaperCTDependencies, get_config

logger = logging.getLogger(__name__)


async def get_info(query: str, history: List[str], deps: PaperCTDependencies, **kwargs) -> str:
    """
    Process a query using the Cell agent.

    Args:
        query: The user query
        history: The conversation history
        deps: The dependencies for the agent
        model: Optional model override

    Returns:
        The agent's response
    """
    logger.info(f"QUERY: {query}")
    logger.debug(f"HISTORY: {history}")

    if history:
        query += "\n\n## Previous Conversation:\n"
        for h in history:
            query += f"\n{h}"

    result = await celltype_agent.run(query, deps=deps, **kwargs)
    return result.data


def chat(deps: Optional[PaperCTDependencies] = None, model=None, **kwargs):
    """
    Create a Gradio chat interface for the Paper Cell Type agent.

    Args:
        deps: Optional dependencies configuration
        model: Optional model override
        kwargs: Additional keyword arguments for dependencies

    Returns:
        A Gradio ChatInterface
    """
    if deps is None:
        deps = get_config()

        for key, value in kwargs.items():
            if hasattr(deps, key):
                setattr(deps, key, value)

    def get_info_wrapper(query: str, history: List[str]) -> str:
        """Wrapper for the async get_info function."""
        import asyncio
        return asyncio.run(get_info(query, history, deps, **kwargs))

    return gr.ChatInterface(
        fn=get_info_wrapper,
        type="messages",
        title="Cell AI Assistant",
        description="""This assistant helps you search and analyze Cell Ontology.""",
        examples=[
            ["Search for papers on CRISPR gene editing"],
        ],
    )