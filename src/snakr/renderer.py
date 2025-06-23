"""Module for rendering import dependency trees in different formats."""

import os
from typing import TYPE_CHECKING, Protocol

import networkx as nx

from snakr.dependency import DepGraph, ImportType

if TYPE_CHECKING:
    import pygraphviz as pgv


class Renderer(Protocol):
    """Protocol for graph renderers."""

    def render(self, dep_graph: DepGraph) -> None:
        """Render the graph.

        Args:
            dep_graph: a dependency graph `DepGraph` to render
        """
        ...


class GraphvizRenderer:
    """Renderer that outputs the dependency graph in Graphviz (dot) format."""

    def __init__(self, output_path: str = "out.png") -> None:
        """
        Initialize the renderer.

        Args:
            output_path: Optional path to write the dot file. If None, prints to stdout.
        """
        self.output_path = output_path

    def render(self, dep_graph: DepGraph) -> None:
        """
        Render the dependency graph in Graphviz (dot) format.

        Args:
            dep_graph: The dependency graph to render.
        """

        assert self.output_path, "There must be an output path"
        self._check_pygraphviz()

        agraph: pgv.AGraph = nx.nx_agraph.to_agraph(dep_graph.graph)

        COLOR_MAP = {
            ImportType.FIRST_PARTY: "lightblue",
            ImportType.THIRD_PARTY: "lightgreen",
            ImportType.STDLIB: "lightcoral",
        }
        # Build a cache for O(1) lookup
        module_by_name = {str(n): n for n in dep_graph.graph.nodes}
        for node in agraph.nodes():
            module_obj = module_by_name[node.get_name()]
            color = COLOR_MAP[module_obj.import_type]
            node.attr["color"] = color
            node.attr["style"] = "filled"

        # TODO(alvaro): Explore other layouts
        layout = os.environ.get("SNAKR_LAYOUT") or "dot"
        agraph.layout(layout)
        agraph.draw(self.output_path)

    def _check_pygraphviz(self) -> None:
        try:
            # This import is required for nx.nx_agraph.to_agraph
            import pygraphviz  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "pygraphviz is required for using the graphviz rendered . Install with 'pip install pygraphviz'"
            ) from e
