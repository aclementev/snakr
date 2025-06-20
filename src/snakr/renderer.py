"""Module for rendering import dependency trees in different formats."""

from typing import Protocol

import networkx as nx

from snakr.tree import DepGraph


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

        agraph = nx.nx_agraph.to_agraph(dep_graph.graph)
        agraph.layout("dot")
        agraph.draw(self.output_path)

    def _check_pygraphviz(self) -> None:
        try:
            # This import is required for nx.nx_agraph.to_agraph
            import pygraphviz  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "pygraphviz is required for using the graphviz rendered . Install with 'pip install pygraphviz'"
            ) from e
