"""
Gradio interface for the PaperQA agent.
"""
import os
import logging
from typing import List, Optional, Any

import gradio as gr

from aurelian.utils.async_utils import run_sync
from .annotator_agent import annotator_agent
from .annotator_config import AnnotatorDependencies, get_config

logger = logging.getLogger(__name__)


async def get_info(query: str, history: List[str], deps: AnnotatorDependencies, **kwargs) -> str:
    """
    Process a query using the Annotator agent.

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

    result = await annotator_agent.run(query, deps=deps, **kwargs)
    return result.data


def chat(deps: Optional[AnnotatorDependencies] = None, model=None, **kwargs):
    """
    Create a Gradio chat interface for the Annotator agent.

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
        title="Annotator AI Assistant",
        description="""This assistant helps you annotate cell type data.""",
        examples=[
            ["C_goblet	Colon goblet cells	Colonic goblet cells; Mucus-producing cells; GC	Crypt-resident goblet cells; Intercrypt goblet cells; Early goblet cells"],
        ],
    )