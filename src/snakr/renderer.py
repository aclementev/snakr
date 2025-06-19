"""Module for rendering import dependency trees in different formats."""

from typing import Protocol

from rich.console import Console
from rich.tree import Tree

from snakr.tree import DepGraph


class GraphRenderer(Protocol):
    """Protocol for tree renderers."""

    def render(self, dep_graph: DepGraph) -> None:
        """Render the tree.

        Args:
            node: The root node of the tree to render.
        """
        ...


# TODO(alvaro): A graphviz/dot renderer


class RichGraphRenderer:
    """Renderer that outputs trees using the rich library."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the renderer.

        Args:
            console: Optional rich Console instance. If not provided, a new one will be created.
        """
        self.console = console or Console()

    def render(self, dep_graph: DepGraph) -> None:
        """Render the tree using rich.

        Args:
            dep_graph: The dependency graph to render.
        """
        rich_tree = self._build_rich_tree(dep_graph)
        self.console.print(rich_tree)

    def _build_rich_tree(self, dep_graph: DepGraph) -> Tree:
        """Convert a DepGraph to a rich Tree.

        Args:
            dep_graph: The dependency graph to convert.

        Returns:
            A rich Tree object representing the dependency graph.
        """
        # Find root nodes (nodes with no incoming edges)
        root_nodes = [
            n for n in dep_graph.graph.nodes() if dep_graph.graph.in_degree(n) == 0
        ]

        if not root_nodes:
            return Tree("[red]No dependencies found[/]")

        main_tree = Tree(f"[bold blue]{root_nodes[0].name}[/]")

        def _add_node_to_tree(node, tree, path):
            if node in path:
                # Cycle detected
                tree.add(f"[red]↩ cycle to {node.name}[/]")
                return
            # Skip the root node as it's already added
            if node != root_nodes[0]:
                node_tree = tree.add(f"[blue]{node.name}[/]")
            else:
                node_tree = tree
            new_path = path | {node}
            for child in dep_graph.graph.successors(node):
                _add_node_to_tree(child, node_tree, new_path)

        _add_node_to_tree(root_nodes[0], main_tree, set())

        for root in root_nodes[1:]:
            root_tree = main_tree.add(f"[bold blue]{root.name}[/]")
            _add_node_to_tree(root, root_tree, set())

        return main_tree
