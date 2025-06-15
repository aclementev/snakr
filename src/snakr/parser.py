import ast
import sys
from pathlib import Path
from typing import NamedTuple

import networkx as nx

from snakr.tree import DepGraph, Module


class Import(NamedTuple):
    """Represents an import"""

    left: str
    right: str


def find_module_root(path: Path) -> str | None:
    """Find the root module name given the path of a Python file (its top level parent module)

    This function traverses up the directory tree to find the outermost module name by looking for:
    1. Project root indicators (pyproject.toml or setup.py)
    2. src/ directory (common in modern Python projects)
    3. The outermost directory containing __init__.py

    The function ensures it finds the top-level module by continuing to search up
    until it finds a project root or src directory, rather than stopping at the first
    __init__.py it encounters.

    Args:
        path: Path to a Python module file.

    Returns:
        The name of the outermost module, or None if not found.

    Examples:
        >>> find_module_root(Path("src/foo/bar/baz.py"))
        "foo"
        >>> find_module_root(Path("mypackage/subpackage/module.py"))
        "mypackage"
    """
    assert path.is_file(), "We must have a module file"

    # Search the parents looking for a module
    parent = path.resolve().parent
    current_module = path.stem

    while True:
        # Check if we are already at the root of the project
        if parent == parent.parent or _is_project_root(parent):
            return current_module

        if not _is_python_module(parent):
            # This is a single file module, so we return itself
            # FIXME: Consider flagging this as an entrypoint/main module
            return current_module

        # We are looking at a module, so we can check the parent
        current_module = parent.stem
        parent = parent.parent


def _is_project_root(path: Path) -> bool:
    """Check if a path is the root of a Python project by looking for common indicators.

    Args:
        path: Path to check

    Returns:
        True if the path contains indicators of being a project root, False otherwise
    """
    # Check for common Python project configuration files
    return any(
        (path / f).exists()
        for f in ("pyproject.toml", "setup.cfg", "setup.py", ".git", ".svn")
    )


def path_to_module(path: Path, root_path: Path | None = None) -> str:
    """Convert a Python file path to its fully qualified module name.

    This function takes a path to a Python file and converts it to the module name
    that would be used to import it. It handles various project structures and edge cases.

    Examples:
        - /path/to/project/src/package/module.py -> package.module
        - /path/to/project/src/package/subpackage/module.py -> package.subpackage.module
        - /path/to/project/package/__init__.py -> package
        - /path/to/project/package/subpackage/__init__.py -> package.subpackage

    Args:
        path: Path to the Python file.
        root_path: Optional path to the package root. If not provided, will attempt to find it.

    Returns:
        The fully qualified module name.

    Raises:
        ValueError: If the path does not end in .py
        ValueError: If no package root has been supplied and the package root cannot be determined.
        ValueError: If the file is in an excluded directory (__pycache__, hidden dirs, etc).
    """
    if path.suffix != ".py":
        raise ValueError(f"Path must be a Python file: {path}")

    # Check if file is in an excluded directory
    for part in path.parts:
        if part == "__pycache__" or part.startswith("."):
            raise ValueError(f"File {path} is in an excluded directory: {part}")

    # Find package root if not provided
    if root_path is None:
        root_path = find_module_root(path)
        if root_path is None:
            raise ValueError(f"Could not determine package root for {path}")

    # Get the relative path from the root
    try:
        rel_path = path.relative_to(root_path)
    except ValueError as e:
        raise ValueError(f"Path {path} is not under root {root_path}") from e

    parts = []
    for part in rel_path.parts[:-1]:  # All but the last part (filename)
        parts.append(part)

    # Handle the filename
    filename = rel_path.stem
    if filename != "__init__":
        parts.append(filename)

    return ".".join(parts) if parts else ""


def parse_imports(path: Path) -> DepGraph:
    """Parse all import statements from a Python file.

    Args:
        file_path: Path to the Python file to analyze.

    Returns:
        A set of imported module names.

    Raises:
        FileNotFoundError: If the specified file does not exist.
        SyntaxError: If the file contains invalid Python syntax.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except FileNotFoundError:
        print(f"Error: File '{path}' not found.", file=sys.stderr)
        sys.exit(1)
    except SyntaxError as e:
        print(f"Error parsing file: {e}", file=sys.stderr)
        sys.exit(1)

    graph = nx.DiGraph()
    # XXX(alvaro): This is wrong, we don't want the root, we want the full module! (minus depth normalization)
    current_module = Module(find_module_root(path))
    print("Analyzing", current_module.name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                # Handle dotted imports by taking the first part
                print(
                    f"Found import statement at line {node.lineno}: {name.name} {repr(node)}"
                )
                imported = Module(name.name)
                graph.add_edge(current_module, imported)
        elif isinstance(node, ast.ImportFrom) and node.module:
            # For relative imports, we need to handle the dots
            if node.level > 0:
                # Skip relative imports for now as they require package context
                continue
            print(
                f"Found from import statement at line {node.lineno}: {node.module} {repr(node)}"
            )
            imported = Module(node.module)
            graph.add_edge(current_module, imported)

    return DepGraph(graph)


def _is_python_module(path: Path) -> bool:
    """Check if a directory is a Python module by looking for __init__.py.

    Args:
        path: Path to check

    Returns:
        True if the directory contains __init__.py, False otherwise

    """
    # FIXME(alvaro): Add support for namespace packages (PEP 420)
    return (path / "__init__.py").exists()


if __name__ == "__main__":
    from snakr.tree import visualize_dot

    visualize_dot(
        parse_imports(
            Path("/Users/alvaro/code/snakr/src/snakr/entrypoints/cli.py")
        ).graph
    )
