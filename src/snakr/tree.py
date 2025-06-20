"""Module for representing import dependency trees."""

import itertools
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Hashable, TypeVar

import networkx as nx

_TNode = TypeVar("_TNode", bound=Hashable)


class ImportType(Enum):
    """
    Type of import:
    - FIRST_PARTY: Module is part of the current project (under project root)
    - THIRD_PARTY: Module is installed in site-packages (not stdlib or first-party)
    - STDLIB: Module is part of the Python standard library
    """

    FIRST_PARTY = auto()
    THIRD_PARTY = auto()
    STDLIB = auto()


@dataclass(frozen=True)
class Module:
    name: str
    import_type: ImportType

    def __str__(self) -> str:
        return self.name


class DepGraph:
    """A directed graph representing dependencies between Python modules.

    This class wraps a NetworkX DiGraph to provide a more specific interface
    for working with Python module dependencies. The graph structure allows
    for efficient traversal and analysis of import relationships between modules.

    Attributes:
        graph: The underlying NetworkX directed graph containing the dependency
            relationships between modules.
    """

    def __init__(self, graph: nx.DiGraph) -> None:
        # FIXME(alvaro): Turns out in python sometimes you CAN have import cycles, so we have to
        # just handle them
        # check_acyclic_graph(graph)
        self.graph = graph


def format_cycle(cycle: list[_TNode]) -> str:
    """Format a cycle of nodes into a string representation.

    Args:
        cycle: List of node names forming a cycle.

    Returns:
        str: String representation of the cycle with nodes joined by " -> ".
    """
    # NOTE(alvaro): The simple cycles don't close, so for representation reasons we add the original node at the end of the cycle
    assert len(cycle) > 0, "Cannot represent an empty cycle"
    return " -> ".join(str(node) for node in itertools.chain(cycle, [cycle[0]]))


def print_cycles(graph: nx.DiGraph, cycles: Iterable[list[_TNode]]) -> None:
    for cycle in cycles:
        print(format_cycle(cycle))


def check_acyclic_graph(graph: nx.DiGraph) -> None:
    if not nx.is_directed_acyclic_graph(graph):
        print_cycles(graph, nx.simple_cycles(graph))
        raise ValueError("Dependency graph has cycles")


def visualize_dot(graph: nx.DiGraph, path: str = "graph_dot.png") -> None:
    dot = nx.nx_agraph.to_agraph(graph)
    dot.layout("dot")
    dot.draw(path)
