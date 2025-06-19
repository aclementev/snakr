"""Command line interface for snakr."""

import argparse
import time
from pathlib import Path

from snakr.parser import parse_imports
from snakr.renderer import RichGraphRenderer
from snakr.tree import visualize_dot


def main() -> None:
    """Main entry point for the script.

    Parses command line arguments and displays the import graph for the specified
    Python file.
    """
    parser = argparse.ArgumentParser(
        description="Analyze Python import dependencies in a file."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the Python file to analyze",
    )
    parser.add_argument(
        "--max-depth",
        type=lambda x: int(x)
        if int(x) > 0
        else parser.error("--max-depth must be a positive integer"),
        default=None,
        metavar="N",
        help="Limit the depth of module names in the import graph (positive integer). Default: no limit.",
    )
    parser.add_argument(
        "-i",
        "--ignore-module",
        action="append",
        type=_parse_module_path,
        help="Module name to ignore (can be provided multiple times)",
    )

    args = parser.parse_args()

    if not args.file.exists():
        parser.error(f"File '{args.file}' does not exist")
    if args.file.suffix != ".py":
        parser.error("Input file must be a Python file")
    ignore_modules = set(args.ignore_module or [])

    start = time.perf_counter()
    dep_graph = parse_imports(
        args.file,
        max_depth=args.max_depth,
        ignore_modules=ignore_modules,
    )
    elapsed_s = time.perf_counter() - start
    print(f"elapsed: {elapsed_s:.2f}s")

    # FIXME(alvaro): We need to fix this
    # renderer = RichGraphRenderer()
    # renderer.render(dep_graph)
    visualize_dot(dep_graph.graph)


def _parse_module_path(x: str) -> str:
    """
    Check if the string is a valid Python module path.

    A valid module path consists of one or more dot-separated identifiers,
    where each identifier starts with a letter or underscore and is followed by
    letters, digits, or underscores.

    Examples of valid module paths:
        - foo
        - foo.bar
        - _foo.bar2


    Args:
        s: The string to check.

    Returns:
        True if s is a valid module path, False otherwise.
    """
    import re

    # Python identifier: [a-zA-Z_][a-zA-Z0-9_]*
    identifier = r"[a-zA-Z_][a-zA-Z0-9_]*"
    module_path_pattern = rf"^{identifier}(?:\.{identifier})*$"
    if not re.match(module_path_pattern, x):
        raise argparse.ArgumentTypeError("the supplied module is not a valid module")
    return x


if __name__ == "__main__":
    main()
