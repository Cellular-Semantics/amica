"""CXG annotation workflow definition and orchestration helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from amica.services import (
    DatasetLoader,
    ExpansionService,
    GroundingService,
    PublicationFetcher,
)
from amica.utils.cxg import (
    CxgPipelineSettings,
    CxgResourceLayout,
    PreparedAnnotationBundle,
)

from .definitions import GraphNode, WorkflowGraph
from .graph_agent import GraphDependencies


def build_cxg_annotate_graph() -> WorkflowGraph:
    """Declarative workflow describing the CXG annotation pipeline."""

    nodes = [
        GraphNode(
            id="prepare_data",
            description=(
                "Load CXG TSV inputs, normalise annotation records, and download any "
                "required publication text assets."
            ),
            service="cxg.prepare_data",
            next=["expand_full_names"],
        ),
        GraphNode(
            id="expand_full_names",
            description=(
                "Given grouped annotations and publication text, call the paper cell "
                "type agent to expand shorthand cell labels into richer metadata."
            ),
            service="cxg.expand_full_names",
            next=["ground_annotations"],
        ),
        GraphNode(
            id="ground_annotations",
            description=(
                "Invoke the ontology annotator to ground enriched cell type entries "
                "against the Cell Ontology and persist per-dataset reports."
            ),
            service="cxg.ground_annotations",
            next=[],
        ),
    ]

    return WorkflowGraph(
        name="cxg_annotate",
        entrypoint="prepare_data",
        nodes=nodes,
    )


@dataclass
class CxgGraphDependencies(GraphDependencies):
    """Graph dependencies bundled with CXG-specific services."""

    settings: CxgPipelineSettings = field(default_factory=CxgPipelineSettings)
    layout: CxgResourceLayout = field(default_factory=CxgResourceLayout)
    dataset_loader: DatasetLoader | None = None
    publication_fetcher: PublicationFetcher | None = None
    expansion_service: ExpansionService | None = None
    grounding_service: GroundingService | None = None
    bundle: PreparedAnnotationBundle | None = None

    def __post_init__(self) -> None:
        self.layout.ensure_directories()
        self.dataset_loader = self.dataset_loader or DatasetLoader(
            self.layout, self.settings
        )
        self.publication_fetcher = self.publication_fetcher or PublicationFetcher(
            self.layout
        )
        self.expansion_service = self.expansion_service or ExpansionService(
            self.layout, self.settings
        )
        self.grounding_service = self.grounding_service or GroundingService(
            self.layout, self.settings
        )


NodeHandler = Callable[[CxgGraphDependencies], Awaitable[str | None]]


async def run_cxg_workflow(
    *,
    settings: CxgPipelineSettings | None = None,
    layout: CxgResourceLayout | None = None,
    deps: CxgGraphDependencies | None = None,
) -> PreparedAnnotationBundle:
    """Execute the CXG workflow graph using the registered service handlers."""

    graph = build_cxg_annotate_graph()
    if deps is None:
        deps = CxgGraphDependencies(
            graph=graph,
            settings=settings or CxgPipelineSettings.from_env(),
            layout=layout or CxgResourceLayout.from_env(),
        )
    else:
        deps.graph = graph

    node_id = graph.entrypoint
    while node_id:
        node = deps.graph.route(node_id)
        handler = _SERVICE_HANDLERS.get(node.service)
        if not handler:
            raise ValueError(f"No service handler registered for '{node.service}'")
        node_id = await handler(deps)

    if not deps.bundle:
        raise RuntimeError("CXG workflow completed without producing a bundle.")
    return deps.bundle


async def _handle_prepare_data(deps: CxgGraphDependencies) -> str:
    loader = deps.dataset_loader
    fetcher = deps.publication_fetcher
    if not loader or not fetcher:
        raise RuntimeError("Dataset loader or publication fetcher not configured.")

    bundle = loader.load()
    fetcher.ensure_text_assets(bundle.article_to_annotations.keys())
    deps.bundle = bundle
    return "expand_full_names"


async def _handle_expand_full_names(deps: CxgGraphDependencies) -> str:
    bundle = _require_bundle(deps)
    if not deps.expansion_service:
        raise RuntimeError("Expansion service not configured.")
    await deps.expansion_service.expand_annotations(bundle)
    return "ground_annotations"


async def _handle_ground_annotations(deps: CxgGraphDependencies) -> None:
    bundle = _require_bundle(deps)
    if not deps.grounding_service:
        raise RuntimeError("Grounding service not configured.")
    await deps.grounding_service.ground_annotations(bundle)
    return None


def _require_bundle(deps: CxgGraphDependencies) -> PreparedAnnotationBundle:
    if not deps.bundle:
        raise RuntimeError(
            "Workflow bundle missing. Ensure prepare_data runs before other nodes."
        )
    return deps.bundle


_SERVICE_HANDLERS: dict[str, NodeHandler] = {
    "cxg.prepare_data": _handle_prepare_data,
    "cxg.expand_full_names": _handle_expand_full_names,
    "cxg.ground_annotations": _handle_ground_annotations,
}


__all__ = ["build_cxg_annotate_graph", "CxgGraphDependencies", "run_cxg_workflow"]
