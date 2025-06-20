"""Tests for the parser module."""

from pathlib import Path

import pytest

from snakr.dependency import ImportType
from snakr.parser import (
    find_module,
    find_module_root,
    get_module_root_path,
    path_to_module,
)


@pytest.mark.parametrize(
    "path_parts,expected_module",
    [
        # Basic module paths
        pytest.param(
            ["src", "package", "module.py"], "package.module", id="package.module"
        ),
        pytest.param(
            ["src", "package", "subpackage", "module.py"],
            "package.subpackage.module",
            id="package.subpackage.module",
        ),
        # Init files
        pytest.param(["package", "__init__.py"], "package", id="package"),
        pytest.param(
            ["package", "subpackage", "__init__.py"],
            "package.subpackage",
            id="package.subpackage",
        ),
        # Without src directory
        pytest.param(["package", "module.py"], "package.module", id="package.module"),
        pytest.param(
            ["package", "subpackage", "module.py"],
            "package.subpackage.module",
            id="package.subpackage.module",
        ),
    ],
)
def test_module_path_conversion(tmp_path, path_parts, expected_module):
    """Test module path conversion for various valid paths.

    Args:
        tmp_path: The root directory of the project.
        path_parts: List of path components to create the test file path.
        expected_module: The expected module name after conversion.
    """
    path = tmp_path.joinpath(*path_parts)
    # FIXME(alvaro): When we have root finding logic we won't need this
    root_path = tmp_path / "src" if path_parts[0] == "src" else tmp_path
    assert path_to_module(path, root_path=root_path) == expected_module


def test_excluded_directories(tmp_path):
    """Test that files in excluded directories raise ValueError."""
    # Test __pycache__
    path = tmp_path / "package" / "__pycache__" / "module.py"
    path.parent.mkdir(parents=True)
    path.touch()

    with pytest.raises(ValueError, match="is in an excluded directory: __pycache__"):
        path_to_module(path, root_path=tmp_path)

    # Test hidden directory
    path = tmp_path / "package" / ".hidden" / "module.py"
    path.parent.mkdir(parents=True)
    path.touch()

    with pytest.raises(ValueError, match="is in an excluded directory: .hidden"):
        path_to_module(path, root_path=tmp_path)


def test_non_python_file(tmp_path):
    """Test that non-Python files raise ValueError."""
    path = tmp_path / "package" / "module.txt"
    path.parent.mkdir(parents=True)
    path.touch()

    with pytest.raises(ValueError, match="must be a Python file"):
        path_to_module(path, root_path=tmp_path)


def test_path_not_under_root(tmp_path):
    """Test that paths not under the root raise ValueError."""
    other_root = Path("/other/root")
    path = other_root / "package" / "module.py"

    with pytest.raises(ValueError, match="is not under root"):
        path_to_module(path, root_path=tmp_path)


@pytest.mark.parametrize(
    "path_parts,expected_module",
    [
        # Single file modules
        pytest.param(["foo.py"], "foo", id="single_file"),
        pytest.param(["foo", "bar.py"], "foo", id="single_file_in_dir"),
        # src/ layout
        pytest.param(["src", "foo", "bar.py"], "foo", id="src_single_file_in_dir"),
        # __init__.py files
        pytest.param(["foo", "__init__.py"], "foo", id="init_file"),
        pytest.param(["foo", "bar", "__init__.py"], "foo", id="init_file_in_subdir"),
        # Nested modules
        pytest.param(["foo", "bar", "baz.py"], "foo", id="nested_module"),
        pytest.param(["src", "foo", "__init__.py"], "foo", id="src_init_file"),
        pytest.param(
            ["src", "foo", "bar", "__init__.py"], "foo", id="src_init_file_in_subdir"
        ),
        pytest.param(["foo", "bar", "baz", "qux.py"], "foo", id="deeply_nested_module"),
        pytest.param(
            ["foo", "bar", "baz", "__init__.py"], "foo", id="deeply_nested_init"
        ),
        pytest.param(
            ["foo", "bar", "baz", "qux", "__init__.py"],
            "foo",
            id="deeply_nested_init_in_subdir",
        ),
    ],
)
def test_find_module_root(tmp_path, path_parts, expected_module):
    """Test finding the root module name for various file paths.

    Args:
        tmp_path: The root directory of the project.
        path_parts: List of path components to create the test file path.
        expected_module: The expected root module name.
    """
    # Create the directory structure
    path = tmp_path.joinpath(*path_parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()

    _add_init_files(path, root=tmp_path)

    assert find_module_root(path) == expected_module


@pytest.mark.parametrize(
    "root_indicator",
    [
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        ".git",
        ".svn",
    ],
)
def test_find_module_root_with_various_indicators(tmp_path, root_indicator):
    """Test that find_module_root handles various project root indicators correctly.

    Args:
        tmp_path: The root directory of the project.
        root_indicator: The file or directory that indicates a project root.
    """
    # Create the project root indicator
    if root_indicator in (".git", ".svn"):
        (tmp_path / root_indicator).mkdir()
    else:
        (tmp_path / root_indicator).touch()

    # Create a module structure
    path = tmp_path / "src" / "foo" / "bar.py"
    path.parent.mkdir(parents=True)
    path.touch()
    (path.parent / "__init__.py").touch()

    assert find_module_root(path) == "foo"


def test_find_module_root_with_nested_vcs(tmp_path):
    """Test that find_module_root correctly identifies the outermost project root.

    This test verifies that when we have nested version control directories,
    we correctly identify the outermost one as the project root.
    """
    # Create nested .git directories
    outer_git = tmp_path / ".git"
    outer_git.mkdir()

    inner_dir = tmp_path / "inner"
    inner_dir.mkdir()
    inner_git = inner_dir / ".git"
    inner_git.mkdir()

    # Create a module structure under the inner directory
    path = inner_dir / "src" / "foo" / "bar.py"
    path.parent.mkdir(parents=True)
    path.touch()
    (path.parent / "__init__.py").touch()

    # Should return "foo" because we should stop at the outermost .git
    assert find_module_root(path) == "foo"


def test_find_module_root_not_a_file(tmp_path):
    """Test that find_module_root raises AssertionError for non-file paths."""
    path = tmp_path / "not_a_file"
    path.mkdir()

    with pytest.raises(AssertionError, match="We must have a module file"):
        find_module_root(path)


def _add_init_files(path, root):
    # Create __init__.py files in parent directories if needed
    current = path.parent
    while current != root and current.name != "src":
        (current / "__init__.py").touch()
        current = current.parent


@pytest.mark.parametrize(
    "path_parts,expected_root_parts",
    [
        pytest.param(["foo.py"], ["."], id="single_file"),
        pytest.param(["foo", "bar.py"], ["foo"], id="single_file_in_dir"),
        pytest.param(
            ["src", "foo", "bar.py"], ["src", "foo"], id="src_single_file_in_dir"
        ),
        pytest.param(["foo", "__init__.py"], ["foo"], id="init_file"),
        pytest.param(["foo", "bar", "__init__.py"], ["foo"], id="init_file_in_subdir"),
        pytest.param(["foo", "bar", "baz.py"], ["foo"], id="nested_module"),
        pytest.param(["src", "foo", "__init__.py"], ["src", "foo"], id="src_init_file"),
        pytest.param(
            ["src", "foo", "bar", "__init__.py"],
            ["src", "foo"],
            id="src_init_file_in_subdir",
        ),
        pytest.param(
            ["foo", "bar", "baz", "qux.py"],
            ["foo"],
            id="deeply_nested_module",
        ),
        pytest.param(
            ["foo", "bar", "baz", "__init__.py"],
            ["foo"],
            id="deeply_nested_init",
        ),
        pytest.param(
            ["foo", "bar", "baz", "qux", "__init__.py"],
            ["foo"],
            id="deeply_nested_init_in_subdir",
        ),
    ],
)
def test_get_module_root_path(tmp_path, path_parts, expected_root_parts):
    """Test get_module_root_path returns the correct Path for various module layouts."""
    path = tmp_path.joinpath(*path_parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    _add_init_files(path, root=tmp_path)
    expected = tmp_path.joinpath(*expected_root_parts)
    assert get_module_root_path(path) == expected


def _tree(path: Path, prefix: str = ""):
    """Print the directory tree of the given path, using unicode characters for pretty output."""
    if not path.exists():
        print(f"{path} [does not exist]")
        return

    def inner(current_path: Path, prefix: str = ""):
        entries = sorted(
            list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower())
        )
        entries_count = len(entries)
        for idx, entry in enumerate(entries):
            connector = "└── " if idx == entries_count - 1 else "├── "
            print(prefix + connector + entry.name)
            if entry.is_dir():
                extension = "    " if idx == entries_count - 1 else "│   "
                inner(entry, prefix + extension)

    print(path.name)
    if path.is_dir():
        inner(path)


@pytest.mark.parametrize(
    "module_name,expected_type",
    [
        ("collections", ImportType.STDLIB),
        ("networkx", ImportType.THIRD_PARTY),
        ("snakr.parser", ImportType.FIRST_PARTY),
    ],
)
def test_import_type_detection(module_name, expected_type):
    result = find_module(module_name, parent_module="snakr")
    assert result is not None
    assert result.import_type == expected_type


def test_import_type_detection_missing():
    result = find_module("this_module_does_not_exist_12345", parent_module="snakr")
    assert result is None
