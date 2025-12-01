from __future__ import annotations

import pytest

from amica.graphs import GraphNode, WorkflowGraph


@pytest.mark.unit
def test_workflow_graph_routing() -> None:
    graph = WorkflowGraph(
        name="demo",
        entrypoint="alpha",
        nodes=[
            GraphNode(id="alpha", description="first", service="svc_a", next=["beta"]),
            GraphNode(id="beta", description="second", service="svc_b"),
        ],
    )
    node = graph.route("beta")
    assert node.service == "svc_b"
    with pytest.raises(KeyError):
        graph.route("missing")

