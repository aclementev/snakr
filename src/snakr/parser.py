import ast
import collections
import importlib.machinery
import importlib.util
from pathlib import Path
from typing import NamedTuple

import networkx as nx

from snakr.dependency import DepGraph, ImportType, Module
from snakr.utils.module import find_module_root, path_to_module
from snakr.utils.stdlib import is_stdlib
from snakr.utils.submodule import is_submodule, trim_module


class ImportResult(NamedTuple):
    name: str
    path: Path | None
    import_type: ImportType


def is_first_party_module(module: str, parent_module: str) -> bool:
    """
    Check if the module is a submodule (or the same module) as parent_module.

    Args:
        module: The module name to check (e.g., 'foo.bar.baz').
        parent_module: The parent module name (e.g., 'foo').

    Returns:
        True if module is the same as parent_module or a submodule of parent_module, False otherwise.
    """
    return is_submodule(module, parent_module)


def find_module(module_name: str, parent_module: str) -> ImportResult | None:
    """
    Resolve a module name to its file path using importlib.util.find_spec.

    Args:
        module_name: The fully qualified module name (e.g., 'snakr.parser').

    Returns:
        Path to the module's .py file, or None if not found or is a namespace/built-in/frozen package.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        # This is most likely a guarded import that is not relevant and should be ignored, but could
        # also mean trouble... hard to distinguish
        return None
    if not spec:
        return None

    if is_stdlib(spec):
        path = spec.origin if spec.origin not in ("built-in", "frozen") else None
        return ImportResult(module_name, path=path, import_type=ImportType.STDLIB)

    # Determine if first-party or third-party
    path = Path(spec.origin) if spec.origin else None
    import_type = (
        ImportType.FIRST_PARTY
        if is_first_party_module(module_name, parent_module=parent_module)
        else ImportType.THIRD_PARTY
    )
    return ImportResult(module_name, path, import_type=import_type)


class ImportParser(ast.NodeVisitor):
    """A node visitor implementation for parsing AST to detect imports in files"""

    def __init__(self, max_depth: int | None = None):
        self.max_depth = max_depth
        self.imports: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for name in node.names:
            imported_name = trim_module(name.name, depth=self.max_depth)
            self.imports.append(imported_name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # Skip relative imports (level > 0)
        if node.level > 0 or not node.module:
            return
        imported_name = trim_module(node.module, depth=self.max_depth)
        self.imports.append(imported_name)
        self.generic_visit(node)

    def get_imports(self) -> list[str]:
        return self.imports


def parse_imports(
    path: Path, max_depth: int | None = None, ignore_modules: set[str] | None = None
) -> DepGraph:
    """
    Recursively parse all import statements from a Python file and its dependencies, including parent package __init__.py files in correct order.

    Args:
        path: Path to the Python file to analyze.
        recurse_stdlib: Whether to recurse into stdlib modules (default: False).

    Returns:
        DepGraph: A directed graph of module dependencies.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        SyntaxError: If the file contains invalid Python syntax.
    """
    queue = collections.deque()
    processed = set()
    ignore_modules = ignore_modules or set()
    nodes = {}
    edges = []

    def _is_ignored_module(module: str) -> bool:
        return any(is_submodule(module, ignored) for ignored in ignore_modules)

    def _queue_module_and_parents(module_name: str):
        """
        Queue all parent packages' __init__.py modules and the target module itself,
        ensuring each is only queued if not already processed. Also, add edges from each child to its parent.
        """
        parts = module_name.split(".")
        parent_packages = [".".join(parts[:i]) for i in range(1, len(parts))]
        all_to_queue = parent_packages + [module_name]
        for child, parent in zip(all_to_queue[1:], all_to_queue[:-1]):
            if child and parent:
                edges.append((child, parent))
        for mod in all_to_queue:
            if mod and mod not in processed and not _is_ignored_module(mod):
                queue.append(mod)

    # Seed with the initial module and its parents
    start_module = path_to_module(path)
    parent_module = find_module_root(path)

    if _is_ignored_module(start_module):
        raise ValueError("The initial module cannot be in the ignored modules")

    _queue_module_and_parents(start_module)

    while queue:
        module_name = queue.popleft()
        if _is_ignored_module(module_name):
            continue
        if module_name in processed:
            continue
        processed.add(module_name)

        module_result = find_module(module_name, parent_module=parent_module)
        if module_result is None:
            continue
        nodes[module_name] = Module(module_name, import_type=module_result.import_type)

        if module_result.import_type == ImportType.STDLIB:
            continue
        try:
            with open(module_result.path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (FileNotFoundError, SyntaxError):
            continue

        visitor = ImportParser(max_depth=max_depth)
        visitor.visit(tree)
        imported_modules = visitor.get_imports()
        for imported_name in imported_modules:
            if imported_name not in processed and not _is_ignored_module(imported_name):
                edges.append((module_name, imported_name))
                _queue_module_and_parents(imported_name)

    graph = nx.DiGraph()
    graph.add_nodes_from(nodes.values())
    graph.add_edges_from(
        (
            (nodes[left], nodes[right])
            for left, right in edges
            if left in nodes and right in nodes
        )
    )
    return DepGraph(graph)


if __name__ == "__main__":
    from snakr.dependency import visualize_dot

    visualize_dot(
        parse_imports(
            Path("/Users/alvaro/code/snakr/src/snakr/entrypoints/cli.py")
        ).graph
    )
