import ast
import collections
import importlib.machinery
import importlib.util
import sysconfig
from pathlib import Path
from typing import NamedTuple

import networkx as nx

from snakr.dependency import DepGraph, ImportType, Module


def find_module_root(path: Path) -> str:
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
        root_path = get_module_root_path(path)
        if root_path is None:
            raise ValueError(f"Could not determine package root for {path}")

    # Get the relative path from the root
    try:
        rel_path = path.absolute().relative_to(root_path.parent)
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
    return _is_submodule(module, parent_module)


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


def is_stdlib(spec: importlib.machinery.ModuleSpec) -> bool:
    """
    Check if a given module path is part of the Python standard library.

    Args:
        spec: The importlib.machinery.ModuleSpec object for the module.

    Returns:
        True if the module is in the stdlib, False otherwise.
    """
    stdlib_path = Path(sysconfig.get_paths()["stdlib"]).resolve()
    module_origin = getattr(spec, "origin", None)
    if not module_origin or module_origin in ("built-in", "frozen"):
        return False
    module_path = Path(module_origin)
    try:
        return module_path.resolve().is_relative_to(stdlib_path)
    except AttributeError:
        # For Python <3.9, fallback to manual check
        return str(module_path.resolve()).startswith(str(stdlib_path))
        # For Python <3.9, fallback to manual check
        return str(module_path.resolve()).startswith(str(stdlib_path))


def trim_module(module_name: str, depth: int | None) -> str:
    if depth is None:
        return module_name
    assert depth > 0, "depth cannot be less than 0"
    return ".".join(module_name.split(".")[:depth])


def _is_submodule(module: str, parent: str) -> bool:
    """
    Check if a module is a submodule (or the same module) as another module.

    Args:
        module: The module name to check (e.g., 'foo.bar.baz').
        parent: The parent module name (e.g., 'foo.bar').

    Returns:
        True if module is the same as parent or a submodule of parent, False otherwise.

    Examples:
        >>> _is_submodule('foo.bar.baz', 'foo.bar')
        True
        >>> _is_submodule('foo.bar', 'foo.bar')
        True
        >>> _is_submodule('foo.bar', 'foo')
        True
        >>> _is_submodule('foo', 'foo.bar')
        False
        >>> _is_submodule('foo.bar', 'foo.bar.baz')
        False
    """
    if module == parent:
        return True
    return module.startswith(parent + ".")


def parse_imports(
    path: Path, max_depth: int | None = None, ignore_modules: set[str] | None = None
) -> DepGraph:
    """
    Recursively parse all import statements from a Python file and its dependencies.

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

    # FIXME(alvaro): This is a O(k) check
    def _is_ignored_module(module: str) -> bool:
        return any(_is_submodule(module, ignored) for ignored in ignore_modules)

    # Seed with the initial module
    start_module = path_to_module(path)
    parent_module = find_module_root(path)

    queue.append(start_module)
    if _is_ignored_module(start_module):
        raise ValueError("The initial module cannot be in the ignored modules")

    nodes = {}
    edges = []
    while queue:
        module_name = queue.popleft()
        # Skip if in ignore_modules or is a submodule of any ignored module
        if _is_ignored_module(module_name):
            continue
        if module_name in processed:
            continue
        processed.add(module_name)
        # print("Processing", module_name)

        module_result = find_module(module_name, parent_module=parent_module)
        if module_result is None:
            continue
        nodes[module_name] = Module(module_name, import_type=module_result.import_type)

        if module_result.import_type == ImportType.STDLIB:
            # FIXME(alvaro): We don't support recursing into stdlib modules, which many of them cannot be parsed anyway
            continue
        try:
            with open(module_result.path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (FileNotFoundError, SyntaxError):
            continue
        # FIXME(alvaro): I belive our import recursion is not correct: we need to handle also automatic
        # import of __init__.py files of all of the module levels
        # FIXME(alvaro): We also need to handle from imports with level >0 (what are they?)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imported_name = trim_module(name.name, depth=max_depth)
                    if imported_name not in processed and not _is_ignored_module(
                        imported_name
                    ):
                        edges.append((module_name, imported_name))
                        queue.append(imported_name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level > 0:
                    continue  # Skip relative imports for now
                imported_name = trim_module(node.module, depth=max_depth)
                if imported_name not in processed and not _is_ignored_module(
                    imported_name
                ):
                    edges.append((module_name, imported_name))
                    queue.append(imported_name)

    # Build the graph
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes.values())
    graph.add_edges_from(
        (
            (nodes[left], nodes[right])
            for left, right in edges
            # Remove the invalid nodes
            if left in nodes and right in nodes
        )
    )
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


def get_module_root_path(path: Path) -> Path:
    """Return the Path to the root of the module tree for the input file.

    This function traverses up the directory tree from the given Python file,
    looking for the outermost directory that is still a Python module (contains __init__.py),
    or stops at the project root indicator (pyproject.toml, setup.py, etc).

    Args:
        path: Path to a Python module file.

    Returns:
        Path to the root of the module tree (directory containing __init__.py or just below project root).

    Raises:
        AssertionError: If the input path is not a file.

    Examples:
        >>> get_module_root_path(Path("src/foo/bar/baz.py"))
        Path("src/foo")
        >>> get_module_root_path(Path("mypackage/subpackage/module.py"))
        Path("mypackage")
    """
    assert path.is_file(), "We must have a module file"
    parent = path.resolve().parent
    last_module_dir = parent
    while True:
        if parent == parent.parent or _is_project_root(parent):
            break
        if not _is_python_module(parent):
            break
        last_module_dir = parent
        parent = parent.parent
    return last_module_dir


if __name__ == "__main__":
    from snakr.dependency import visualize_dot

    visualize_dot(
        parse_imports(
            Path("/Users/alvaro/code/snakr/src/snakr/entrypoints/cli.py")
        ).graph
    )
