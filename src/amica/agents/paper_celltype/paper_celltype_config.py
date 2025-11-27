"""
Configuration for the Cell agent.
"""
import os

from dataclasses import dataclass, field
from typing import Optional

from aurelian.dependencies.workdir import HasWorkdir, WorkDir

@dataclass
class PaperCTDependencies(HasWorkdir):

    llm: str = field(
        default="gpt-4.1-2025-04-14",
        metadata={
            "description": "LLM to use for queries and answer generation. Default is gpt-4.1-2025-04-14."}
    )
    summary_llm: str = field(
        default="gpt-4.1-2025-04-14",
        metadata={"description": "LLM to use for summarization. Default is gpt-4.1-2025-04-14."}
    )
    embedding: str = field(
        default="text-embedding-3-small",
        metadata={"description": "Embedding model to use. Default is text-embedding-3-small."}
    )
    temperature: float = field(
        default=0.1,
        metadata={"description": "Temperature for LLM generation. Default is 0.1."}
    )

    workdir: Optional[WorkDir] = None

    def __post_init__(self):
        """Initialize the config with default values."""
        if self.workdir is None:
            self.workdir = WorkDir()


def get_config() -> PaperCTDependencies:
    """
    Get the Paper Cell Type agent configuration from environment variables or defaults.

    Returns:
        A PaperCTDependencies instance with default settings.

    Note:
        Users can modify the returned object to customize settings.
        Example:
            ```python
            deps = get_config()
            deps.llm = "claude-3-sonnet-20240229"  # Use Claude instead of default GPT-4
            deps.temperature = 0.5  # Increase temperature
            deps.evidence_k = 15  # Retrieve more evidence
            ```
    """
    workdir_path = os.environ.get("AURELIAN_WORKDIR", None)
    workdir = WorkDir(location=workdir_path) if workdir_path else None

    return PaperCTDependencies(
        workdir=workdir,
    )