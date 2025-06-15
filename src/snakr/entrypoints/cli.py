"""Command line interface for snakr."""

import argparse
from pathlib import Path

from snakr.parser import parse_imports
from snakr.renderer import RichTreeRenderer


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

    args = parser.parse_args()

    if not args.file.exists():
        parser.error(f"File '{args.file}' does not exist")
    if args.file.suffix != ".py":
        parser.error("Input file must be a Python file")

    dep_graph = parse_imports(args.file)
    renderer = RichTreeRenderer()
    renderer.render(dep_graph)


if __name__ == "__main__":
    main()
