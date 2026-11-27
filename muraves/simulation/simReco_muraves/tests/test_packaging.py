"""The repository's pyproject.toml must describe simReco_muraves completely.

setuptools installs only the packages listed in the root pyproject.toml,
so a subpackage added under simReco_muraves but not listed there would be
missing from a regular installation without any error.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import simReco_muraves

tomllib = pytest.importorskip("tomllib")  # standard library from Python 3.11

PACKAGE = "simReco_muraves"
PACKAGE_DIR = Path(simReco_muraves.__file__).resolve().parent


def _root_pyproject() -> tuple[Path, dict]:
    """The repository root and its parsed pyproject.toml."""
    for folder in PACKAGE_DIR.parents:
        candidate = folder / "pyproject.toml"
        if candidate.is_file():
            config = tomllib.loads(candidate.read_text(encoding="utf-8"))
            if config.get("project", {}).get("name") == "muraves-lib":
                return folder, config
    pytest.skip("not inside the MURAVES Software repository")


def _listed_packages() -> set[str]:
    _, config = _root_pyproject()
    return {
        name for name in config["tool"]["setuptools"]["packages"]
        if name.split(".")[0] == PACKAGE
    }


def _packages_on_disk() -> set[str]:
    names = set()
    for init_file in PACKAGE_DIR.rglob("__init__.py"):
        relative = init_file.parent.relative_to(PACKAGE_DIR)
        names.add(".".join((PACKAGE, *relative.parts)))
    return names


def test_every_subpackage_is_listed():
    missing = sorted(_packages_on_disk() - _listed_packages())
    assert not missing, f"add these to packages in the root pyproject.toml: {missing}"


def test_every_listed_package_exists():
    stale = sorted(_listed_packages() - _packages_on_disk())
    assert not stale, f"listed in the root pyproject.toml but not on disk: {stale}"


def test_package_dir_points_at_this_package():
    root, config = _root_pyproject()
    mapped = config["tool"]["setuptools"]["package-dir"][PACKAGE]
    assert (root / mapped).resolve() == PACKAGE_DIR


def test_every_command_points_at_a_function():
    _, config = _root_pyproject()
    commands = {
        name: target for name, target in config["project"]["scripts"].items()
        if target.startswith(PACKAGE + ".")
    }
    assert commands, "no simReco_muraves commands registered"

    for name, target in commands.items():
        module_name, function_name = target.split(":")
        module = importlib.import_module(module_name)
        assert callable(getattr(module, function_name, None)), f"{name} -> {target}"
