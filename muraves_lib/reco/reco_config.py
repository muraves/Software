"""Reconstruction configuration shared by the MURAVES data and simulation chains.

The parameters ship with ``muraves_lib`` in ``muraves_lib/configuration/``:

* ``shared/reco_parameters.json``: parameters used by both chains;
* ``data/data_parameters.json``: parameters used only by the data chain;
* ``simulation/``: parameters used only by the simulation chain (none yet).

Each value is defined in exactly one file: a chain file may not redefine a section
of the shared file.

The configuration is built in layers, each one deep-merged on top of the previous:

1. ``shared/reco_parameters.json`` plus the file of the requested chain (always loaded);
2. an optional *base* file;
3. an optional *override* file, for one-off changes.

The chain is given with ``chain="data"`` / ``chain="simulation"`` (or the
``MURAVES_RECO_CHAIN`` environment variable); without one only the shared
parameters are loaded.

The base and override files may only contain keys that exist in the package files
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
RUNTIME_CHAIN_ENV = "MURAVES_RECO_CHAIN"

CONFIGURATION_DIR = Path(__file__).resolve().parents[1] / "configuration"
SHARED_CONFIG_PATH = CONFIGURATION_DIR / "shared" / "reco_parameters.json"
CHAIN_CONFIG_PATHS = {
    "data": CONFIGURATION_DIR / "data" / "data_parameters.json",
    "simulation": CONFIGURATION_DIR / "simulation" / "simulation_parameters.json",
}


def package_config_paths(chain: str | None = None) -> list[Path]:
    """Package parameter files loaded for ``chain``: the shared file, then the chain's own.

    A chain without its own file yet (simulation) loads the shared file only.
    """
    paths = [SHARED_CONFIG_PATH]
    if chain is not None:
        if chain not in CHAIN_CONFIG_PATHS:
            raise ValueError(
                f"Unknown reconstruction chain {chain!r}; expected one of {sorted(CHAIN_CONFIG_PATHS)}"
            )
        if CHAIN_CONFIG_PATHS[chain].exists():
            paths.append(CHAIN_CONFIG_PATHS[chain])
    return paths


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


def _check_layer(
    layer: dict[str, Any], reference: dict[str, Any], path: Path, reference_paths: list[Path]
) -> None:
    problems = _unknown_keys(layer, reference)
    if problems:
        raise ValueError(
            f"Configuration file {path} has keys that are not reconstruction parameters: "
            + ", ".join(problems)
            + ". Valid keys are those of "
            + " + ".join(str(p) for p in reference_paths)
            + "."
        )


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file {path} must contain a JSON object")
    return data


def _load_package_config(chain: str | None) -> tuple[dict[str, Any], list[Path]]:
    """Merge the shared parameters with the chain's own, refusing redefinitions."""
    paths = package_config_paths(chain)
    config = _load_json(paths[0])
    for chain_path in paths[1:]:
        chain_config = _load_json(chain_path)
        duplicated = sorted(
            key for key in chain_config if not key.startswith("_") and key in config
        )
        if duplicated:
            raise ValueError(
                f"{chain_path} redefines sections of {paths[0]}: {', '.join(duplicated)}. "
                "Each parameter must be defined in one file only."
            )
        config = _deep_merge(config, chain_config)
    return config, paths


def set_runtime_config_path(
    config_path: Path | str | None,
    base_config_path: Path | str | None = None,
    chain: str | None = None,
) -> None:
    if config_path is None:
        os.environ.pop(RUNTIME_CONFIG_ENV, None)
    else:
        os.environ[RUNTIME_CONFIG_ENV] = str(Path(config_path).expanduser().resolve())

    if base_config_path is None:
        os.environ.pop(RUNTIME_BASE_CONFIG_ENV, None)
    else:
        os.environ[RUNTIME_BASE_CONFIG_ENV] = str(Path(base_config_path).expanduser().resolve())

    if chain is None:
        os.environ.pop(RUNTIME_CHAIN_ENV, None)
    else:
        package_config_paths(chain)  # validate the name
        os.environ[RUNTIME_CHAIN_ENV] = chain

    # Clear the cache when config paths change
    _load_reco_config_cached.cache_clear()


@functools.lru_cache(maxsize=1)
def _load_reco_config_cached(
    config_path: str | None,
    base_config_path: str | None,
    chain: str | None,
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

    package, package_paths = _load_package_config(chain)
    config = package

    if base_candidate is not None:
        if not base_candidate.exists():
            raise FileNotFoundError(f"Base configuration file not found: {base_candidate}")
        base = _load_json(base_candidate)
        _check_layer(base, package, base_candidate, package_paths)
        config = _deep_merge(config, base)

    if candidate is not None and candidate != base_candidate:
        if not candidate.exists():
            raise FileNotFoundError(f"Configuration override file not found: {candidate}")
        override = _load_json(candidate)
        _check_layer(override, package, candidate, package_paths)
        config = _deep_merge(config, override)

    return config


def get_reco_config(
    config_path: Path | str | None = None,
    base_config_path: Path | str | None = None,
    chain: str | None = None,
) -> dict[str, Any]:
    """Load reconstruction configuration with caching.

    The package parameters of ``chain`` (shared + chain file; shared only when no
    chain is given) are always loaded; ``base_config_path`` and ``config_path``
    (or the corresponding runtime environment variables) are merged on top.
    
    Configuration is cached after first load to avoid repeated file I/O.
    Call set_runtime_config_path() with new paths to invalidate the cache.
    """
    # Convert to strings for hashability in lru_cache
    config_str = str(Path(config_path).expanduser().resolve()) if config_path else None
    base_str = str(Path(base_config_path).expanduser().resolve()) if base_config_path else None
    
    if chain is None:
        chain = os.environ.get(RUNTIME_CHAIN_ENV) or None

    return _load_reco_config_cached(config_str, base_str, chain)


def resolve_first_existing(paths: list[str]) -> Path:
    for item in paths:
        candidate = Path(item)
        if candidate.exists():
            return candidate
    return Path(paths[-1])
