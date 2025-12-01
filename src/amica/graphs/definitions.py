"""Pydantic-powered graph primitives for orchestrating workflows."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    """Atomic unit within a workflow graph."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    description: str
    service: str
    next_nodes: list[str] = Field(default_factory=list, alias="next")


class WorkflowGraph(BaseModel):
    """Declarative workflow definition validated via Pydantic."""

    name: str
    entrypoint: str
    nodes: list[GraphNode]

    def route(self, node_id: str) -> GraphNode:
        """Return the node configuration for the given identifier."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"Node '{node_id}' not found in workflow graph '{self.name}'")
