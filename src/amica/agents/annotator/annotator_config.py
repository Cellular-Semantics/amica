"""
Configuration for the Ontology Mapper agent.
"""
from dataclasses import dataclass, field
import os
from typing import List, Optional

from aurelian.dependencies.workdir import HasWorkdir, WorkDir


@dataclass
class AnnotatorDependencies(HasWorkdir):
    """
    Configuration for the ontology annotator agent.

    We include a default set of ontologies because the initial text embedding index is slow.
    this can easily be changed e.g. in command line
    """

    def __post_init__(self):
        """Initialize the config with default values."""
        # HasWorkdir doesn't have a __post_init__ method, so we don't call super()
        if self.workdir is None:
            self.workdir = WorkDir()


def get_config(ontologies: Optional[List[str]] = None) -> AnnotatorDependencies:
    """Get the Ontology Mapper configuration from environment variables or defaults."""
    workdir_path = os.environ.get("AURELIAN_WORKDIR", None)
    workdir = WorkDir(location=workdir_path) if workdir_path else None

    config = AnnotatorDependencies(workdir=workdir)

    return config