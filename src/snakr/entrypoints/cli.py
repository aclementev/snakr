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
        help="Limit the depth of module names in the import graph (positive integer). Default: no limit.",
    )

    args = parser.parse_args()

    if not args.file.exists():
        parser.error(f"File '{args.file}' does not exist")
    if args.file.suffix != ".py":
        parser.error("Input file must be a Python file")

    start = time.perf_counter()
    dep_graph = parse_imports(args.file, max_depth=args.max_depth)
    elapsed_s = time.perf_counter() - start
    print(f"elapsed: {elapsed_s:.2f}s")

    # FIXME(alvaro): We need to fix this
    # renderer = RichGraphRenderer()
    # renderer.render(dep_graph)
    visualize_dot(dep_graph.graph)


if __name__ == "__main__":
    main()
