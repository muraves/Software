"""Reconstruction configuration shared by the MURAVES data and simulation chains.

All parameters live in a single file shipped with this package,
``data/reco_parameters.json``; each of its sections states in ``_used_by`` whether
the data chain, the simulation chain or both read it.

The configuration is built in layers, each one deep-merged on top of the previous:

1. ``data/reco_parameters.json`` (always loaded);
2. an optional *base* file (by default the data workflow passes the package file itself);
3. an optional *override* file, for one-off changes.

The base and override files may only contain keys that exist in the package file
(keys starting with ``_`` are documentation and always allowed): a misspelled key or
a key in the wrong section raises an error instead of being silently ignored.
"""
from __future__ import annotations

import functools
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

RUNTIME_CONFIG_ENV = "MURAVES_RECO_CONFIG"
RUNTIME_BASE_CONFIG_ENV = "MURAVES_RECO_BASE_CONFIG"
PACKAGE_CONFIG_PATH = Path(__file__).resolve().parent / "data" / "reco_parameters.json"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _unknown_keys(layer: dict[str, Any], reference: dict[str, Any], prefix: str = "") -> list[str]:
    """Keys of ``layer`` that do not exist in ``reference``, as dotted paths.

    A section (dict) given where the reference has a value, or a value given where
    the reference has a section, is reported too, since merging it would either be
    ignored or wipe out the whole section.
    """
    problems: list[str] = []
    for key, value in layer.items():
        if key.startswith("_"):
            continue
        path = f"{prefix}{key}"
        if key not in reference:
            problems.append(f"'{path}' (unknown key)")
        elif isinstance(reference[key], dict) != isinstance(value, dict):
            expected = "a section" if isinstance(reference[key], dict) else "a value"
            problems.append(f"'{path}' (expected {expected})")
        elif isinstance(value, dict):
            problems.extend(_unknown_keys(value, reference[key], prefix=f"{path}."))
    return problems


def _check_layer(layer: dict[str, Any], reference: dict[str, Any], path: Path) -> None:
    problems = _unknown_keys(layer, reference)
    if problems:
        raise ValueError(
            f"Configuration file {path} has keys that are not reconstruction parameters: "
            + ", ".join(problems)
            + f". Valid keys are those of {PACKAGE_CONFIG_PATH}."
        )


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file {path} must contain a JSON object")
    return data


def set_runtime_config_path(
    config_path: Path | str | None,
    base_config_path: Path | str | None = None,
) -> None:
    if config_path is None:
        os.environ.pop(RUNTIME_CONFIG_ENV, None)
    else:
        os.environ[RUNTIME_CONFIG_ENV] = str(Path(config_path).expanduser().resolve())

    if base_config_path is None:
        os.environ.pop(RUNTIME_BASE_CONFIG_ENV, None)
    else:
        os.environ[RUNTIME_BASE_CONFIG_ENV] = str(Path(base_config_path).expanduser().resolve())

    # Clear the cache when config paths change
    _load_reco_config_cached.cache_clear()


@functools.lru_cache(maxsize=1)
def _load_reco_config_cached(
    config_path: str | None,
    base_config_path: str | None,
) -> dict[str, Any]:
    """Internal cached version of config loading. Paths must be strings for hashability."""
    base_candidate: Path | None
    if base_config_path is not None:
        base_candidate = Path(base_config_path).expanduser().resolve()
    else:
        configured_base = os.environ.get(RUNTIME_BASE_CONFIG_ENV)
        base_candidate = Path(configured_base).expanduser().resolve() if configured_base else None

    candidate: Path | None
    if config_path is not None:
        candidate = Path(config_path).expanduser().resolve()
    else:
        configured = os.environ.get(RUNTIME_CONFIG_ENV)
        candidate = Path(configured).expanduser().resolve() if configured else None

    package = _load_json(PACKAGE_CONFIG_PATH)
    config = package

    if base_candidate is not None:
        if not base_candidate.exists():
            raise FileNotFoundError(f"Base configuration file not found: {base_candidate}")
        base = _load_json(base_candidate)
        _check_layer(base, package, base_candidate)
        config = _deep_merge(config, base)

    if candidate is not None and candidate != base_candidate:
        if not candidate.exists():
            raise FileNotFoundError(f"Configuration override file not found: {candidate}")
        override = _load_json(candidate)
        _check_layer(override, package, candidate)
        config = _deep_merge(config, override)

    return config


def get_reco_config(
    config_path: Path | str | None = None,
    base_config_path: Path | str | None = None,
) -> dict[str, Any]:
    """Load reconstruction configuration with caching.

    The package defaults are always loaded; ``base_config_path`` and ``config_path``
    (or the corresponding runtime environment variables) are merged on top.
    
    Configuration is cached after first load to avoid repeated file I/O.
    Call set_runtime_config_path() with new paths to invalidate the cache.
    """
    # Convert to strings for hashability in lru_cache
    config_str = str(Path(config_path).expanduser().resolve()) if config_path else None
    base_str = str(Path(base_config_path).expanduser().resolve()) if base_config_path else None
    
    return _load_reco_config_cached(config_str, base_str)


def resolve_first_existing(paths: list[str]) -> Path:
    for item in paths:
        candidate = Path(item)
        if candidate.exists():
            return candidate
    return Path(paths[-1])
