from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Sequence

from SearchFileName import Search_File
from ClusterLists import CreateClusterList
from evaluate_angular_coordinates import TrackAngularCoordinates
from ReadEvent import ReadEvent
from Tracking import MakeTracks
from reco_config import get_reco_config, resolve_first_existing, set_runtime_config_path


def _mean_rms(values: Sequence[float]) -> tuple[float, float]:
    """Return arithmetic mean and population RMS for a sequence."""
    if not values:
        return 0.0, 0.0
    mean = sum(values) / len(values)
    rms = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    return mean, rms


def _read_slow_control(
    slow_control_path: Path, run: int, config: dict
) -> tuple[float, float, float]:
    trigger_rate = 0.0
    temperature = 0.0
    working_point = 0.0

    if not slow_control_path.exists():
        return trigger_rate, temperature, working_point

    slow_control_cfg = config["slow_control"]
    delimiter = str(slow_control_cfg["delimiter"])
    minimum_fields = int(slow_control_cfg["minimum_fields"])
    run_index = int(slow_control_cfg["run_index"])
    trigger_rate_index = int(slow_control_cfg["trigger_rate_index"])
    temperature_index = int(slow_control_cfg["temperature_index"])
    working_point_index = int(slow_control_cfg["working_point_index"])

    with slow_control_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            fields = raw_line.rstrip("\n").split(delimiter)
            if len(fields) < minimum_fields:
                continue

            try:
                sc_run = int(float(fields[run_index]))
            except ValueError:
                continue

            if sc_run == run:
                try:
                    trigger_rate = float(fields[trigger_rate_index])
                except ValueError:
                    trigger_rate = 0.0
                try:
                    temperature = float(fields[temperature_index])
                except ValueError:
                    temperature = 0.0
                try:
                    working_point = float(fields[working_point_index])
                except ValueError:
                    working_point = 0.0
                break

    return trigger_rate, temperature, working_point


def _load_spiroc_mapping(spiroc_cfg: Path) -> list[int]:
    strips: list[int] = []
    channels: list[int] = []

    with spiroc_cfg.open("r", encoding="utf-8", errors="ignore") as handle:
        for idx, line in enumerate(handle):
            if idx == 0:
                continue
            fields = line.strip().split()
            if len(fields) < 2:
                continue
            try:
                strip = int(fields[0])
                channel = int(fields[1])
            except ValueError:
                continue
            strips.append(strip)
            channels.append(channel)

    # Reorder channel ids by strip number to match the strip-wise ordering used downstream.
    ordered = sorted(range(len(strips)), key=lambda i: strips[i])
    return [channels[i] for i in ordered]


def _load_telescope_config(telescope_cfg: Path) -> tuple[list[int], list[str]]:
    n_stations: list[int] = []
    views: list[str] = []

    with telescope_cfg.open("r", encoding="utf-8", errors="ignore") as handle:
        for idx, line in enumerate(handle):
            if idx == 0:
                continue
            fields = line.split()
            # Expected columns: n_mod n_scheda n_station n_plane type ...
            if len(fields) < 5:
                continue
            try:
                n_station = int(fields[2])
            except ValueError:
                continue
            n_stations.append(n_station)
            views.append(fields[4])

    if not n_stations or not views:
        raise ValueError(
            f"No valid board configuration could be parsed from telescope file: {telescope_cfg}"
        )

    if len(n_stations) != len(views):
        raise ValueError(
            f"Malformed telescope configuration in {telescope_cfg}: "
            f"n_stations={len(n_stations)} differs from views={len(views)}"
        )

    return n_stations, views


def _load_pedestals(
    pedestal_folder: Path,
    n_boards: int,
    sorted_channels: Sequence[int],
) -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
    boards_peds: list[list[float]] = []
    boards_onephes: list[list[float]] = []
    boards_is_copy: list[list[float]] = []

    for board_n in range(n_boards):
        ped_file = pedestal_folder / f"pedestal_{board_n}"

        peds: list[float] = []
        onephes: list[float] = []
        is_copy: list[float] = []

        if ped_file.exists():
            with ped_file.open("r", encoding="utf-8", errors="ignore") as handle:
                for idx, line in enumerate(handle):
                    if idx == 0:
                        continue
                    fields = line.strip().split()
                    if len(fields) < 3:
                        continue
                    try:
                        peds.append(float(fields[1]))
                    except ValueError:
                        peds.append(0.0)
                    try:
                        onephes.append(float(fields[2]))
                    except ValueError:
                        onephes.append(1.0)

                    if len(fields) > 3:
                        try:
                            is_copy.append(float(fields[3]))
                        except ValueError:
                            is_copy.append(0.0)
                    else:
                        is_copy.append(0.0)

        # Keep the same strip ordering used by C++ via sorted channel map.
        sorted_peds = [peds[ch] if 0 <= ch < len(peds) else 0.0 for ch in sorted_channels]
        sorted_onephes = [onephes[ch] if 0 <= ch < len(onephes) else 1.0 for ch in sorted_channels]
        sorted_is_copy = [is_copy[ch] if 0 <= ch < len(is_copy) else 0.0 for ch in sorted_channels]

        boards_peds.append(sorted_peds)
        boards_onephes.append(sorted_onephes)
        boards_is_copy.append(sorted_is_copy)

    return boards_peds, boards_onephes, boards_is_copy


def _safe_get(container: Sequence[Sequence[float]], idx: int) -> Sequence[float]:
    return container[idx] if 0 <= idx < len(container) else []


def _is_sequence(value: object) -> bool:
    return isinstance(value, (list, tuple))


# Hardcoded branch type schema: skip type inference for known branches.
# Maps branch name -> (target_dtype, is_nested)
# is_nested=True means the branch values are lists of lists and need encoding
BRANCH_TYPE_SCHEMA = {
    # Scalar int branches
    "Run": ("int64", False),
    "Nclusters_Z1": ("int64", False),
    "Nclusters_Z2": ("int64", False),
    "Nclusters_Z3": ("int64", False),
    "Nclusters_Z4": ("int64", False),
    "Nclusters_Y1": ("int64", False),
    "Nclusters_Y2": ("int64", False),
    "Nclusters_Y3": ("int64", False),
    "Nclusters_Y4": ("int64", False),
    "Ntracks_3p_xz": ("int64", False),
    "Ntracks_3p_xy": ("int64", False),
    "TriggerMaskSize": ("int64", False),
    "WorkingPoint": ("int64", False),
    
    # Scalar float branches
    "Temperature": ("float64", False),
    "TriggerRate": ("float64", False),
    
    # Nested (list of lists) branches - these need encoding
    "Intercept_4p_xz": ("float64", True),
    "Slope_4p_xz": ("float64", True),
    "chiSquare_4p_xz": ("float64", True),
    "displacement_p4_xz": ("float64", True),
    "Intercept_4p_xy": ("float64", True),
    "Slope_4p_xy": ("float64", True),
    "chiSquare_4p_xy": ("float64", True),
    "displacement_p4_xy": ("float64", True),
    "cluster_c4_index_xz": ("int64", True),
    "cluster_c4_index_xy": ("int64", True),
    "ScatteringAngle_xz": ("float64", True),
    "ScatteringAngle_xy": ("float64", True),
    "Intercept_3p_xz": ("float64", True),
    "Slope_3p_xz": ("float64", True),
    "chiSquare_3p_xz": ("float64", True),
    "Intercept_3p_xy": ("float64", True),
    "Slope_3p_xy": ("float64", True),
    "chiSquare_3p_xy": ("float64", True),
    
    # List branches (list of scalars, not nested)
    "ClusterSize_Z1": ("int64", False),
    "ClusterSize_Z2": ("int64", False),
    "ClusterSize_Z3": ("int64", False),
    "ClusterSize_Z4": ("int64", False),
    "ClusterSize_Y1": ("int64", False),
    "ClusterSize_Y2": ("int64", False),
    "ClusterSize_Y3": ("int64", False),
    "ClusterSize_Y4": ("int64", False),
    "ClusterZ1_Texp": ("float64", False),
    "ClusterZ2_Texp": ("float64", False),
    "ClusterZ3_Texp": ("float64", False),
    "ClusterZ4_Texp": ("float64", False),
    "ClusterY1_Texp": ("float64", False),
    "ClusterY2_Texp": ("float64", False),
    "ClusterY3_Texp": ("float64", False),
    "ClusterY4_Texp": ("float64", False),
    "ClusterEnergy_Z1": ("float64", False),
    "ClusterEnergy_Z2": ("float64", False),
    "ClusterEnergy_Z3": ("float64", False),
    "ClusterEnergy_Z4": ("float64", False),
    "ClusterEnergy_Y1": ("float64", False),
    "ClusterEnergy_Y2": ("float64", False),
    "ClusterEnergy_Y3": ("float64", False),
    "ClusterEnergy_Y4": ("float64", False),
    "ClusterPosition_Z1": ("float64", False),
    "ClusterPosition_Z2": ("float64", False),
    "ClusterPosition_Z3": ("float64", False),
    "ClusterPosition_Z4": ("float64", False),
    "ClusterPosition_Y1": ("float64", False),
    "ClusterPosition_Y2": ("float64", False),
    "ClusterPosition_Y3": ("float64", False),
    "ClusterPosition_Y4": ("float64", False),
    "StripsEnergy_Z1": ("float64", False),
    "StripsEnergy_Z2": ("float64", False),
    "StripsEnergy_Z3": ("float64", False),
    "StripsEnergy_Z4": ("float64", False),
    "StripsEnergy_Y1": ("float64", False),
    "StripsEnergy_Y2": ("float64", False),
    "StripsEnergy_Y3": ("float64", False),
    "StripsEnergy_Y4": ("float64", False),
    "StripsPosition_Z1": ("float64", False),
    "StripsPosition_Z2": ("float64", False),
    "StripsPosition_Z3": ("float64", False),
    "StripsPosition_Z4": ("float64", False),
    "StripsPosition_Y1": ("float64", False),
    "StripsPosition_Y2": ("float64", False),
    "StripsPosition_Y3": ("float64", False),
    "StripsPosition_Y4": ("float64", False),
    "StripsID_Z1": ("int64", False),
    "StripsID_Z2": ("int64", False),
    "StripsID_Z3": ("int64", False),
    "StripsID_Z4": ("int64", False),
    "StripsID_Y1": ("int64", False),
    "StripsID_Y2": ("int64", False),
    "StripsID_Y3": ("int64", False),
    "StripsID_Y4": ("int64", False),
    "TrackCluster_z1_index": ("int64", False),
    "TrackCluster_z2_index": ("int64", False),
    "TrackCluster_z3_index": ("int64", False),
    "TrackCluster_y1_index": ("int64", False),
    "TrackCluster_y2_index": ("int64", False),
    "TrackCluster_y3_index": ("int64", False),
    "Residue_Track3p_z1": ("float64", False),
    "Residue_Track3p_z2": ("float64", False),
    "Residue_Track3p_z3": ("float64", False),
    "Residue_Track3p_y1": ("float64", False),
    "Residue_Track3p_y2": ("float64", False),
    "Residue_Track3p_y3": ("float64", False),
    "TrackEnergy_3p_xy": ("float64", False),
    "TrackEnergy_3p_xz": ("float64", False),
    "Plane4th_isIntercepted_xz": ("int64", False),
    "Plane4th_isIntercepted_xy": ("int64", False),
    "BestChi_xy_index": ("int64", False),
    "BestEnergy_xy_index": ("int64", False),
    "BestChi_xz_index": ("int64", False),
    "BestEnergy_xz_index": ("int64", False),
    "BestChi_xy": ("float64", False),
    "BestEnergy_xy": ("float64", False),
    "BestChi_xz": ("float64", False),
    "BestEnergy_xz": ("float64", False),
    "ExpectedPosition_OnPlane4th_xy": ("float64", False),
    "ExpectedPosition_OnPlane4th_xz": ("float64", False),
    "isInTrack_3p_clZ1": ("int64", False),
    "isInTrack_3p_clZ2": ("int64", False),
    "isInTrack_3p_clZ3": ("int64", False),
    "isInTrack_3p_clY1": ("int64", False),
    "isInTrack_3p_clY2": ("int64", False),
    "isInTrack_3p_clY3": ("int64", False),
    "isInTrack_4p_clZ1": ("int64", False),
    "isInTrack_4p_clZ2": ("int64", False),
    "isInTrack_4p_clZ3": ("int64", False),
    "isInTrack_4p_clY1": ("int64", False),
    "isInTrack_4p_clY2": ("int64", False),
    "isInTrack_4p_clY3": ("int64", False),
    "Theta_3p": ("float64", False),
    "Theta_4p": ("float64", False),
    "Phi_3p": ("float64", False),
    "Phi_4p": ("float64", False),
    "BestTrack_3p_xy_index": ("int64", False),
    "BestTrack_3p_xz_index": ("int64", False),
    "Track_3p_of_4p_index_xy": ("int64", False),
    "Track_3p_of_4p_index_xz": ("int64", False),
    "Track_4p_index_xy": ("int64", False),
    "Track_4p_index_xz": ("int64", False),
    "BestTrack_3p_ChiSquare_xy": ("float64", False),
    "BestTrack_3p_ChiSquare_xz": ("float64", False),
    "BestTrack_4p_ChiSquare_xy": ("float64", False),
    "BestTrack_4p_ChiSquare_xz": ("float64", False),
    "BestTracks_ScatteringAngle_xy": ("float64", False),
    "BestTracks_ScatteringAngle_xz": ("float64", False),
    "Best_track_4p_isTexpNULL_xy": ("int64", False),
    "Best_track_4p_isTexpNULL_xz": ("int64", False),
    "timestamp": ("int64", False),
    "TriggerMaskChannels": ("int64", False),
    "TriggerMaskStrips": ("int64", False),
}


def _to_root_branch(
    values: Sequence[object],
    np: object,
    ak: object,
    target_dtype: str | None = None,
) -> object:
    """Convert values to a ROOT-compatible numpy/awkward array.
    
    If target_dtype is provided (e.g., 'int64', 'float64'), use it directly.
    Otherwise, infer from values. Always try to return numpy arrays for ROOT compatibility.
    """
    dtype_map = {
        "int64": np.int64,
        "float64": np.float64,
        "bool": np.bool_,
    }
    
    if target_dtype and target_dtype in dtype_map:
        # Use hardcoded type schema
        dtype = dtype_map[target_dtype]
        try:
            return np.asarray(values, dtype=dtype)
        except (ValueError, TypeError):
            # If explicit conversion fails, try generic numpy conversion
            try:
                return np.asarray(values)
            except (ValueError, TypeError):
                # Last resort: awkward array
                return ak.Array(values)
    
    # Fallback: infer type from values and always prefer numpy
    try:
        if all(isinstance(v, bool) for v in values):
            return np.asarray(values, dtype=np.bool_)
        if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            return np.asarray(values, dtype=np.int64)
        if all(isinstance(v, (int, float, bool)) for v in values):
            return np.asarray(values, dtype=np.float64)
        # Try generic conversion
        return np.asarray(values)
    except (ValueError, TypeError):
        # Only use awkward as absolute last resort
        return ak.Array(values)


def _needs_nested_encoding(values: Sequence[object]) -> bool:
    for value in values:
        if not _is_sequence(value):
            continue
        if any(_is_sequence(item) for item in value):
            return True
    return False


def _encode_nested(values: Sequence[object]) -> tuple[list[list[object]], list[list[int]]]:
    # uproot cannot directly write list[list[x]] as a single branch in this schema.
    flat_values: list[list[object]] = []
    item_counts: list[list[int]] = []

    for value in values:
        if not _is_sequence(value):
            flat_values.append([])
            item_counts.append([])
            continue

        flat_event: list[object] = []
        count_event: list[int] = []

        for item in value:
            if _is_sequence(item):
                count_event.append(len(item))
                flat_event.extend(item)
            elif item is None:
                count_event.append(0)
            else:
                count_event.append(1)
                flat_event.append(item)

        flat_values.append(flat_event)
        item_counts.append(count_event)

    return flat_values, item_counts


def _build_root_payload(
    columns: dict[str, Sequence[object]],
    np: object,
    ak: object,
) -> tuple[dict[str, object], list[str]]:
    """Build ROOT payload with hardcoded type schema for efficiency."""
    payload: dict[str, object] = {}
    nested_keys: list[str] = []

    for key, values in columns.items():
        # Check schema first
        schema_info = BRANCH_TYPE_SCHEMA.get(key)
        if schema_info:
            target_dtype, is_nested = schema_info
            if is_nested and _needs_nested_encoding(values):
                flat_values, _item_counts = _encode_nested(values)
                payload[key] = _to_root_branch(flat_values, np, ak, target_dtype)
                nested_keys.append(key)
            else:
                payload[key] = _to_root_branch(values, np, ak, target_dtype)
        else:
            # No schema info: fall back to runtime detection
            if _needs_nested_encoding(values):
                flat_values, _item_counts = _encode_nested(values)
                payload[key] = _to_root_branch(flat_values, np, ak)
                nested_keys.append(key)
            else:
                payload[key] = _to_root_branch(values, np, ak)

    return payload, nested_keys


def _resolve_default_output_base(config: dict) -> Path:
    cfg = config["paths"]
    return resolve_first_existing(list(cfg["output_base_candidates"]))


def _resolve_default_raw_base(config: dict) -> Path:
    cfg = config["paths"]
    return resolve_first_existing(list(cfg["raw_base_candidates"]))


def write_root_outputs_direct(
    run: int,
    event_columns: dict[str, list[object]],
    summary: dict[str, object],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write ROOT TTrees directly from in-memory reconstruction payloads."""
    import importlib

    try:
        ak = importlib.import_module("awkward")
        np = importlib.import_module("numpy")
        uproot = importlib.import_module("uproot")
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "required dependency")
        raise RuntimeError(
            f"ROOT export requires optional dependency '{missing}'. "
            "Install uproot and awkward in your environment."
        ) from exc

    export_dir = Path(output_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    print(f"[progress] ROOT direct export started for run={run}", flush=True)

    def to_root_branch(values: Sequence[object]) -> object:
        if all(isinstance(v, bool) for v in values):
            return np.asarray(values, dtype=np.bool_)
        if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            return np.asarray(values, dtype=np.int64)
        if all(isinstance(v, (int, float, bool)) for v in values):
            return np.asarray(values, dtype=np.float64)
        return ak.Array(values)

    def is_sequence(value: object) -> bool:
        return isinstance(value, (list, tuple))

    def needs_nested_encoding(values: Sequence[object]) -> bool:
        for value in values:
            if not is_sequence(value):
                continue
            if any(is_sequence(item) for item in value):
                return True
        return False

    def encode_nested(values: Sequence[object]) -> tuple[list[list[object]], list[list[int]]]:
        # uproot cannot directly write list[list[x]] as a single branch in this schema.
        # Flatten inner lists and store their sizes in a companion __counts branch.
        flat_values: list[list[object]] = []
        item_counts: list[list[int]] = []

        for value in values:
            if not is_sequence(value):
                flat_values.append([])
                item_counts.append([])
                continue

            flat_event: list[object] = []
            count_event: list[int] = []

            for item in value:
                if is_sequence(item):
                    count_event.append(len(item))
                    flat_event.extend(item)
                elif item is None:
                    count_event.append(0)
                else:
                    count_event.append(1)
                    flat_event.append(item)

            flat_values.append(flat_event)
            item_counts.append(count_event)

        return flat_values, item_counts

    def add_payload_branches(
        payload: dict[str, object],
        key: str,
        values: Sequence[object],
        nested_keys: list[str],
    ) -> None:
        if needs_nested_encoding(values):
            #print(f"Branch {key}, needs nested encoding!")
            flat_values, item_counts = encode_nested(values)
            payload[key] = to_root_branch(flat_values)
            # Store only flat values like in c++ code
            #payload[f"{key}__counts"] = to_root_branch(item_counts)
            nested_keys.append(key)
            return
        payload[key] = to_root_branch(values)

    analyzed_payload: dict[str, object] = {}
    analyzed_nested_keys: list[str] = []
    if event_columns:
        for key, values in event_columns.items():
            add_payload_branches(analyzed_payload, key, values, analyzed_nested_keys)
    else:
        analyzed_payload["Run"] = np.asarray([], dtype=np.int64)
        analyzed_payload["Event"] = np.asarray([], dtype=np.int64)

    if analyzed_nested_keys:
        preview = ", ".join(analyzed_nested_keys[:8])
        if len(analyzed_nested_keys) > 8:
            preview += ", ..."
        print(
            "[progress] Encoded nested event branches for ROOT compatibility: "
            f"{preview}",
            flush=True,
        )

    run_info_payload: dict[str, object] = {}
    run_info_nested_keys: list[str] = []
    for key, value in summary.items():
        if isinstance(value, str):
            # Keep Run_info numeric/object payload ROOT-friendly.
            continue
        add_payload_branches(run_info_payload, key, [value], run_info_nested_keys)

    if not run_info_payload:
        run_info_payload["Run"] = np.asarray([run], dtype=np.int64)

    if run_info_nested_keys:
        print(
            "[progress] Encoded nested Run_info branches for ROOT compatibility: "
            + ", ".join(run_info_nested_keys),
            flush=True,
        )

    analyzed_root = export_dir / f"MURAVES_AnalyzedData_run{run}.root"
    run_info_root = export_dir / f"MURAVES_miniRunTree_run{run}.root"

    with uproot.recreate(analyzed_root) as root_file:
        # mktree(payload) writes once; avoid extend() here to prevent duplicated entries.
        tree = root_file.mktree("AnalyzedData", analyzed_payload)
        #tree.extend(analyzed_payload)

    with uproot.recreate(run_info_root) as root_file:
        # Same pattern for run-level tree.
        tree = root_file.mktree("Run_info", run_info_payload)
        #tree.extend(run_info_payload)

    print(
        f"[progress] ROOT direct export completed: {analyzed_root.name}, {run_info_root.name}",
        flush=True,
    )

    return analyzed_root, run_info_root


def run_reconstruction(
    color: str,
    run: int,
    output_base: Path,
    raw_base: Path,
    tracks_base: Path,
    progress_every: int = 1000,
    root_chunk_size: int = 1000,
    config: dict | None = None,
) -> tuple[Path, Path]:
    """Run full event reconstruction for one run and write ROOT outputs directly."""
    print(" ~~~~~~~  Welcome to the MURAVES reconstruction (Python) ~~~~~~~~")
    total_start_wall_time = time.time()

    import importlib

    try:
        ak = importlib.import_module("awkward")
        np = importlib.import_module("numpy")
        uproot = importlib.import_module("uproot")
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "required dependency")
        raise RuntimeError(
            f"ROOT export requires optional dependency '{missing}'. "
            "Install uproot and awkward in your environment."
        ) from exc

    cfg = config or get_reco_config()
    geometry_cfg = cfg["detector_geometry"]
    reco_cfg = cfg["reconstruction"]
    path_cfg = cfg["paths"]

    # Geometry
    if color not in geometry_cfg:
        raise ValueError(f"Unsupported detector color: {color}")
    z_add = [float(v) for v in geometry_cfg[color]["z_add"]]
    x_pos = [float(v) for v in geometry_cfg[color]["x_pos"]]

    y_add = [float(v) for v in reco_cfg["y_add"]]

    # SPACIAL RESOLUTION PARAMETERS (C++ values: sigma_z=0.0040, sigma_y=0.0035)
    sigma_z = float(reco_cfg["sigma_z"])
    sigma_y = float(reco_cfg["sigma_y"])

    # CLUSTERING PARAMETERS (C++ values: s1=6, s2=10, s3=2)
    cluster_cfg = reco_cfg["cluster_thresholds"]
    s1 = float(cluster_cfg["s1"]) # cluster strips must have at least this energy to be seed
    s2 = float(cluster_cfg["s2"]) # single strip clusters must have at least this energy to be accepted as 1-strip cluster
    s3 = float(cluster_cfg["s3"]) # adiacent strips must have at least this energy to be merged into cluster

    # TRACKING PARAMETERS
    # C++ code uses 5*sigma_z and 5*sigma_y as proximity cuts for track building, we keep the same values here.
    proximity_multiplier = float(reco_cfg["proximity_sigma_multiplier"])
    proximity_cut_xz = proximity_multiplier * sigma_z # from C++ comment: "point-trackcandidate distance requirement"
    proximity_cut_xy = proximity_multiplier * sigma_y # from C++ comment: "point-trackcandidate distance requirement"

    # CONSTANT PARAMETERS
    n_boards = int(reco_cfg["n_boards"])
    n_channels = int(reco_cfg["n_channels"])
    # additional parameter available in C++ but not used: 
    #const int nInfo = 168;
    #const int nChInfo = 5;
    #const double FirstStripPos = -0.528;
    #const double AdiacentStripsDistance = 0.0165;

    # PATHS
    reconstructed_path = output_base / str(path_cfg.get("reconstructed_dirname", "RECONSTRUCTED")) / color
    reconstructed_path.mkdir(parents=True, exist_ok=True)

    mini_summary_json = reconstructed_path / f"MURAVES_miniRunTree_run{run}.json"
    analyzed_root_target = reconstructed_path / f"MURAVES_AnalyzedData_run{run}.root"
    run_info_root_target = reconstructed_path / f"MURAVES_miniRunTree_run{run}.root"

    adc_prefix = (
        output_base
        / str(path_cfg["parsed_dirname"])
        / color
        / str(path_cfg["default_data_version"])
        / f"ADC_run{run}.txt"
    )
    complete_adc_file = Search_File(str(adc_prefix))
    if complete_adc_file == "NOTaFIle":
        raise FileNotFoundError(f"ADC input file not found for pattern: {adc_prefix}*")

    print(f"[progress] Input ADC file: {complete_adc_file}", flush=True)

    slow_control_file = raw_base / color / f"{path_cfg['slow_control_prefix']}{run}"
    trigger_rate, temperature, working_point = _read_slow_control(slow_control_file, run, cfg)

    spiroc_cfg = tracks_base / str(path_cfg.get("spiroc_map_relative", "AncillaryFiles/spiroc-hybrid-map.cfg"))
    # The SPiROC mapping file defines the strip-to-channel mapping for each board, which is crucial for correctly interpreting the ADC data and applying pedestals. The C++ code relies on this mapping to reorder channels and access pedestals in the correct order, so we must load it before processing events.
    sorted_channels = _load_spiroc_mapping(spiroc_cfg)

    pedestal_folder = (
        output_base
        / str(path_cfg["pedestal_dirname"])
        / color
        / str(path_cfg["default_data_version"])
        / str(run)
    )
    # Pedestal files contain the baseline ADC values (pedestals) and the conversion factors to photoelectrons (onephes) for each channel. These are essential for calibrating the raw ADC counts into physical energy deposits. The C++ code loads these pedestals before event reconstruction, so we do the same here to ensure that we can apply the correct calibration to each channel's ADC counts during event processing.
    boards_peds, boards_onephes, boards_is1phe_copy = _load_pedestals(
        pedestal_folder, n_boards, sorted_channels
    )

    telescope_cfg = tracks_base / str(path_cfg.get("telescope_cfg_template", "AncillaryFiles/telescope{color}.cfg")).format(color=color)
    n_stations, views = _load_telescope_config(telescope_cfg)
    if len(n_stations) < n_boards or len(views) < n_boards:
        raise ValueError(
            f"Incomplete telescope configuration in {telescope_cfg}: "
            f"expected at least {n_boards} board rows, got {len(n_stations)}"
        )

    # Prepare variables for ADC file reading loop and event reconstruction.
    ev = 0
    n_events_with_3p = 0
    n_events_with_4p = 0
    n_events_with_3p_xy = 0
    n_events_with_3p_xz = 0
    
    # Cluster counts per plane (?) x1, x2, x3, x4: ? - y1, y2, y3, y4: plane with scintillating bars directed along y-axis, i.e. measuring x coordinate ?
    n_events_with_x1_cl = 0
    n_events_with_x2_cl = 0
    n_events_with_x3_cl = 0
    n_events_with_x4_cl = 0
    n_events_with_y1_cl = 0
    n_events_with_y2_cl = 0
    n_events_with_y3_cl = 0
    n_events_with_y4_cl = 0

    n_tracks_xy_3p = 0
    n_tracks_xz_3p = 0
    n_tracks_3p = 0
    n_tracks_xy_4p = 0
    n_tracks_xz_4p = 0
    n_tracks_4p = 0

    n_good_tracks_3p = 0
    n_good_tracks_4p = 0

    first_timestamp = None
    last_timestamp = None

    # (?)
    cluster_energy_acc = {
        "Z1": [],
        "Z2": [],
        "Z3": [],
        "Z4": [],
        "Y1": [],
        "Y2": [],
        "Y3": [],
        "Y4": [],
    }
    ncluster_acc = {
        "Z1": [],
        "Z2": [],
        "Z3": [],
        "Z4": [],
        "Y1": [],
        "Y2": [],
        "Y3": [],
        "Y4": [],
    }

    event_columns_chunk: dict[str, list[object]] = {}
    event_keys: list[str] | None = None
    chunk_events = 0
    root_event_fill_elapsed = 0.0
    root_flush_elapsed = 0.0
    root_run_info_elapsed = 0.0
    analyzed_nested_keys_seen: set[str] = set()

    # READ ADC FILE AND RECONSTRUCT EVENTS
    with uproot.recreate(analyzed_root_target) as analyzed_root_file, Path(
        complete_adc_file
    ).open("r", encoding="utf-8", errors="ignore") as adc_handle:
        analyzed_tree = None

        def flush_root_chunk() -> None:
            nonlocal analyzed_tree, chunk_events, root_flush_elapsed
            if chunk_events == 0:
                return

            flush_start = time.time()
            payload, nested_keys = _build_root_payload(event_columns_chunk, np, ak)
            analyzed_nested_keys_seen.update(nested_keys)

            if analyzed_tree is None:
                analyzed_root_file["AnalyzedData"] = payload
                analyzed_tree = analyzed_root_file["AnalyzedData"]
            else:
                analyzed_tree.extend(payload)

            root_flush_elapsed += time.time() - flush_start

            for values in event_columns_chunk.values():
                values.clear()
            chunk_events = 0

        start_wall_time = time.time()
        for event in adc_handle:
            ev += 1

            event_info = ReadEvent(event, sorted_channels)
            timestamp = event_info.timeStamp

            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp

            trigger_mask_strips = event_info.TrMask_strips
            trigger_mask_channels = event_info.TrMask_channels
            trigger_mask_size = event_info.TrMask_size

            # Deposits per module 
            deposits_p1x1: list[float] = []
            deposits_p1x2: list[float] = []
            deposits_p2x1: list[float] = []
            deposits_p2x2: list[float] = []
            deposits_p3x1: list[float] = []
            deposits_p3x2: list[float] = []
            deposits_p4x1: list[float] = []
            deposits_p4x2: list[float] = []
            deposits_p1y1: list[float] = []
            deposits_p1y2: list[float] = []
            deposits_p2y1: list[float] = []
            deposits_p2y2: list[float] = []
            deposits_p3y1: list[float] = []
            deposits_p3y2: list[float] = []
            deposits_p4y1: list[float] = []
            deposits_p4y2: list[float] = []

            # Time expansions per module
            texp_1x1 = texp_1x2 = texp_2x1 = texp_2x2 = 0.0
            texp_3x1 = texp_3x2 = texp_4x1 = texp_4x2 = 0.0
            texp_1y1 = texp_1y2 = texp_2y1 = texp_2y2 = 0.0
            texp_3y1 = texp_3y2 = texp_4y1 = texp_4y2 = 0.0

            for b in range(n_boards):
                if b >= len(views) or b >= len(n_stations):
                    continue

                view = views[b]
                n_station = n_stations[b]

                adc_counts = event_info.boards[b] if b < len(event_info.boards) else []
                peds_board = boards_peds[b] if b < len(boards_peds) else []
                onephe_board = boards_onephes[b] if b < len(boards_onephes) else []

                time_exp_value = event_info.timeExp[b] if b < len(event_info.timeExp) else 0.0

                if n_station == 1:
                    if view == "x1":
                        texp_1x1 = time_exp_value
                    if view == "x2":
                        texp_1x2 = time_exp_value
                    if view == "y1":
                        texp_1y1 = time_exp_value
                    if view == "y2":
                        texp_1y2 = time_exp_value
                if n_station == 2:
                    if view == "x1":
                        texp_2x1 = time_exp_value
                    if view == "x2":
                        texp_2x2 = time_exp_value
                    if view == "y1":
                        texp_2y1 = time_exp_value
                    if view == "y2":
                        texp_2y2 = time_exp_value
                if n_station == 3:
                    if view == "x1":
                        texp_3x1 = time_exp_value
                    if view == "x2":
                        texp_3x2 = time_exp_value
                    if view == "y1":
                        texp_3y1 = time_exp_value
                    if view == "y2":
                        texp_3y2 = time_exp_value
                if n_station == 4:
                    if view == "x1":
                        texp_4x1 = time_exp_value
                    if view == "x2":
                        texp_4x2 = time_exp_value
                    if view == "y1":
                        texp_4y1 = time_exp_value
                    if view == "y2":
                        texp_4y2 = time_exp_value

                for adc_ch in range(n_channels):
                    adc_count = adc_counts[adc_ch] if adc_ch < len(adc_counts) else 0.0
                    ped = peds_board[adc_ch] if adc_ch < len(peds_board) else 0.0
                    onephe = onephe_board[adc_ch] if adc_ch < len(onephe_board) else 1.0

                    if onephe == 0:
                        deposit = 0.0
                    else:
                        # Convert ADC counts to photoelectron-equivalent deposit.
                        deposit = (adc_count - ped) / onephe

                    if n_station == 1:
                        if view == "x1":
                            deposits_p1x1.append(deposit)
                        if view == "x2":
                            deposits_p1x2.append(deposit)
                        if view == "y1":
                            deposits_p1y1.append(deposit)
                        if view == "y2":
                            deposits_p1y2.append(deposit)
                    if n_station == 2:
                        if view == "x1":
                            deposits_p2x1.append(deposit)
                        if view == "x2":
                            deposits_p2x2.append(deposit)
                        if view == "y1":
                            deposits_p2y1.append(deposit)
                        if view == "y2":
                            deposits_p2y2.append(deposit)
                    if n_station == 3:
                        if view == "x1":
                            deposits_p3x1.append(deposit)
                        if view == "x2":
                            deposits_p3x2.append(deposit)
                        if view == "y1":
                            deposits_p3y1.append(deposit)
                        if view == "y2":
                            deposits_p3y2.append(deposit)
                    if n_station == 4:
                        if view == "x1":
                            deposits_p4x1.append(deposit)
                        if view == "x2":
                            deposits_p4x2.append(deposit)
                        if view == "y1":
                            deposits_p4y1.append(deposit)
                        if view == "y2":
                            deposits_p4y2.append(deposit)

            # Concatenate sub-plane energy deposits to form a full plane deposit. 
            deposits_p1x = deposits_p1x1 + deposits_p1x2
            deposits_p2x = deposits_p2x1 + deposits_p2x2
            deposits_p3x = deposits_p3x1 + deposits_p3x2
            deposits_p4x = deposits_p4x1 + deposits_p4x2

            # Y view uses reversed sub-plane concatenation, same was done in the C++ code. 
            # !!This is a concatenation of lists so it's not commutative!!
            deposits_p1y = deposits_p1y2 + deposits_p1y1
            deposits_p2y = deposits_p2y2 + deposits_p2y1
            deposits_p3y = deposits_p3y2 + deposits_p3y1
            deposits_p4y = deposits_p4y2 + deposits_p4y1

	        #/////////////////////////////////////////////////////////////////////////////////////
	        #//////////////////////////////////            ///////////////////////////////////////
	        #///////////////////////////////// CLUSTERING ///////////////////////////////////////
	        #////////////////////////////////            ///////////////////////////////////////
	        #///////////////////////////////////////////////////////////////////////////////////

            results_p1x = CreateClusterList(
                deposits_p1x,
                s1,
                s2,
                s3,
                texp_1x1,
                texp_1x2,
                # board 0 and 1 are x1 sub-planes
                _safe_get(trigger_mask_strips, 0),
                _safe_get(trigger_mask_strips, 1),
            )
            results_p2x = CreateClusterList(
                deposits_p2x,
                s1,
                s2,
                s3,
                texp_2x1,
                texp_2x2,
                # board 4 and 5 are x2 sub-planes
                _safe_get(trigger_mask_strips, 4),
                _safe_get(trigger_mask_strips, 5),
            )
            results_p3x = CreateClusterList(
                deposits_p3x,
                s1,
                s2,
                s3,
                texp_3x1,
                texp_3x2,
                # board 8 and 9 are x3 sub-planes
                _safe_get(trigger_mask_strips, 8),
                _safe_get(trigger_mask_strips, 9),
            )
            results_p4x = CreateClusterList(
                deposits_p4x,
                s1,
                s2,
                s3,
                texp_4x1,
                texp_4x2,
                # board 12 and 13 are x4 sub-planes
                _safe_get(trigger_mask_strips, 12),
                _safe_get(trigger_mask_strips, 13),
            )

            results_p1y = CreateClusterList(
                deposits_p1y,
                s1,
                s2,
                s3,
                texp_1y2,
                texp_1y1,
                # board 2 and 3 are y1 sub-planes, note the reversed order for y views
                _safe_get(trigger_mask_strips, 3),
                _safe_get(trigger_mask_strips, 2),
            )
            results_p2y = CreateClusterList(
                deposits_p2y,
                s1,
                s2,
                s3,
                texp_2y2,
                texp_2y1,
                # board 6 and 7 are y2 sub-planes, note the reversed order for y views
                _safe_get(trigger_mask_strips, 7),
                _safe_get(trigger_mask_strips, 6),
            )
            results_p3y = CreateClusterList(
                deposits_p3y,
                s1,
                s2,
                s3,
                texp_3y2,
                texp_3y1,
                # board 10 and 11 are y3 sub-planes, note the reversed order for y views
                _safe_get(trigger_mask_strips, 11),
                _safe_get(trigger_mask_strips, 10),
            )
            results_p4y = CreateClusterList(
                deposits_p4y,
                s1,
                s2,
                s3,
                texp_4y2,
                texp_4y1,
                # board 14 and 15 are y4 sub-planes, note the reversed order for y views
                _safe_get(trigger_mask_strips, 15),
                _safe_get(trigger_mask_strips, 14),
            )

            nclusters_z1 = len(results_p1x.ClustersEnergy)
            nclusters_z2 = len(results_p2x.ClustersEnergy)
            nclusters_z3 = len(results_p3x.ClustersEnergy)
            nclusters_z4 = len(results_p4x.ClustersEnergy)

            nclusters_y1 = len(results_p1y.ClustersEnergy)
            nclusters_y2 = len(results_p2y.ClustersEnergy)
            nclusters_y3 = len(results_p3y.ClustersEnergy)
            nclusters_y4 = len(results_p4y.ClustersEnergy)

            # (?) Is this really necessary this change of name from x to z ? To me it's just confusing. 
            # Keeping like this for now to match the C++ code but we should consider refactoring this in the future for clarity.
            if nclusters_z1 > 0:
                n_events_with_x1_cl += 1
            if nclusters_z2 > 0:
                n_events_with_x2_cl += 1
            if nclusters_z3 > 0:
                n_events_with_x3_cl += 1
            if nclusters_z4 > 0:
                n_events_with_x4_cl += 1
            if nclusters_y1 > 0:
                n_events_with_y1_cl += 1
            if nclusters_y2 > 0:
                n_events_with_y2_cl += 1
            if nclusters_y3 > 0:
                n_events_with_y3_cl += 1
            if nclusters_y4 > 0:
                n_events_with_y4_cl += 1

            cluster_energy_acc["Z1"].extend(results_p1x.ClustersEnergy)
            cluster_energy_acc["Z2"].extend(results_p2x.ClustersEnergy)
            cluster_energy_acc["Z3"].extend(results_p3x.ClustersEnergy)
            cluster_energy_acc["Z4"].extend(results_p4x.ClustersEnergy)
            cluster_energy_acc["Y1"].extend(results_p1y.ClustersEnergy)
            cluster_energy_acc["Y2"].extend(results_p2y.ClustersEnergy)
            cluster_energy_acc["Y3"].extend(results_p3y.ClustersEnergy)
            cluster_energy_acc["Y4"].extend(results_p4y.ClustersEnergy)

            ncluster_acc["Z1"].append(nclusters_z1)
            ncluster_acc["Z2"].append(nclusters_z2)
            ncluster_acc["Z3"].append(nclusters_z3)
            ncluster_acc["Z4"].append(nclusters_z4)
            ncluster_acc["Y1"].append(nclusters_y1)
            ncluster_acc["Y2"].append(nclusters_y2)
            ncluster_acc["Y3"].append(nclusters_y3)
            ncluster_acc["Y4"].append(nclusters_y4)

####################################################################################################################################
############################################ DEEPLEY CHECKED UP TO HERE ############################################################
####################################################################################################################################
            tracks_xz = MakeTracks(
                results_p1x.ClustersPositions,
                results_p2x.ClustersPositions,
                results_p3x.ClustersPositions,
                results_p4x.ClustersPositions,
                results_p1x.ClustersEnergy,
                results_p2x.ClustersEnergy,
                results_p3x.ClustersEnergy,
                results_p4x.ClustersEnergy,
                results_p1x.TimeExpansions,
                results_p2x.TimeExpansions,
                results_p3x.TimeExpansions,
                results_p4x.TimeExpansions,
                proximity_cut_xz,
                x_pos,
                z_add,
                sigma_z,
            )
            tracks_xy = MakeTracks(
                results_p1y.ClustersPositions,
                results_p2y.ClustersPositions,
                results_p3y.ClustersPositions,
                results_p4y.ClustersPositions,
                results_p1y.ClustersEnergy,
                results_p2y.ClustersEnergy,
                results_p3y.ClustersEnergy,
                results_p4y.ClustersEnergy,
                results_p1y.TimeExpansions,
                results_p2y.TimeExpansions,
                results_p3y.TimeExpansions,
                results_p4y.TimeExpansions,
                proximity_cut_xy,
                x_pos,
                y_add,
                sigma_y,
            )

            ntracks_3p_xz = len(tracks_xz.intercepts_3p)
            ntracks_3p_xy = len(tracks_xy.intercepts_3p)

            # CALCULATE THE TOTAL NUMBER OF TRACKS IN THE RUN
            ##### we are still inside the event loop, so this is an accumulation of tracks across events.
            n_tracks_xy_3p += ntracks_3p_xy
            n_tracks_xz_3p += ntracks_3p_xz
            n_tracks_3p += ntracks_3p_xy * ntracks_3p_xz
            ###############################################

            if ntracks_3p_xz > 0 and ntracks_3p_xy > 0:
                n_events_with_3p += 1
            if ntracks_3p_xz > 0:
                n_events_with_3p_xz += 1
            if ntracks_3p_xy > 0:
                n_events_with_3p_xy += 1

            best_track_xy_ind = -1
            best_track_xz_ind = -1
            theta_3p = -1.0
            phi_3p = -1.0

            best_track_3p_chi_xy = -1.0
            best_track_3p_chi_xz = -1.0

            # /////////////////////////// 3D BEST TRACK ////////////////////////////////////////
            if ntracks_3p_xz > 0 and ntracks_3p_xy > 0:
                if tracks_xy.BestChi_index == tracks_xy.BestEnergy_index:
                    best_track_xy_ind = tracks_xy.BestEnergy_index
                else:
                    #//// CRITERIA TO CHOOSE THE BEST TRACK BETWEEN BEST CHI AND BEST ENERGY ///////
                    best_track_xy_ind = tracks_xy.BestChi_index

                if tracks_xz.BestChi_index == tracks_xz.BestEnergy_index:
                    best_track_xz_ind = tracks_xz.BestEnergy_index
                else:
                    #//// CRITERIA TO CHOOSE THE BEST TRACK BETWEEN BEST CHI AND BEST ENERGY ///////
                    best_track_xz_ind = tracks_xz.BestChi_index

                if best_track_xz_ind >= 0 and best_track_xy_ind >= 0:
                    coordinates_3p = TrackAngularCoordinates(
                        tracks_xy.slopes_3p[best_track_xy_ind],
                        tracks_xz.slopes_3p[best_track_xz_ind],
                        x_pos[0],
                        x_pos[2],
                    )
                    theta_3p, phi_3p = coordinates_3p
                    n_good_tracks_3p += 1

                    best_track_3p_chi_xy = tracks_xy.chiSquares_3p[best_track_xy_ind]
                    best_track_3p_chi_xz = tracks_xz.chiSquares_3p[best_track_xz_ind]

            n4p_xy = sum(1 for n in tracks_xy.Ntracks_4p if n > 0)
            n4p_xz = sum(1 for n in tracks_xz.Ntracks_4p if n > 0)
            if n4p_xz > 0 and n4p_xy > 0:
                n_events_with_4p += 1
                n_tracks_xy_4p += n4p_xy
                n_tracks_xz_4p += n4p_xz
                n_tracks_4p += n4p_xz * n4p_xy

            # Best 4p track estimation equivalent to C++ selection.
            theta_4p = -1.0
            phi_4p = -1.0
            best_track_4p_chi_xy = -1.0
            best_track_4p_chi_xz = -1.0
            best_scattering_angle_xy = -1.0
            best_scattering_angle_xz = -1.0

            track_3p_of_4p_idx_xy = -1
            track_3p_of_4p_idx_xz = -1
            track_4p_idx_xy = -1
            track_4p_idx_xz = -1
            best_track_4p_is_texp_null_xy = -1
            best_track_4p_is_texp_null_xz = -1

            cluster_c4_texp_xz: list[list[float]] = []
            for idx_row, row in enumerate(tracks_xz.cluster_indices_4):
                texp_row = []
                for idx_val in row:
                    idx_int = int(idx_val)
                    if 0 <= idx_int < len(results_p4x.TimeExpansions):
                        texp_row.append(results_p4x.TimeExpansions[idx_int])
                    else:
                        texp_row.append(-1.0)
                cluster_c4_texp_xz.append(texp_row)

            cluster_c4_texp_xy: list[list[float]] = []
            for idx_row, row in enumerate(tracks_xy.cluster_indices_4):
                texp_row = []
                for idx_val in row:
                    idx_int = int(idx_val)
                    if 0 <= idx_int < len(results_p4y.TimeExpansions):
                        texp_row.append(results_p4y.TimeExpansions[idx_int])
                    else:
                        texp_row.append(-1.0)
                cluster_c4_texp_xy.append(texp_row)
                
	        #////////////////////////////////////////////////////////////////////////////////
	        #////////////////////////////// BEST TRACK 4 PLANES /////////////////////////////
            if tracks_xz.Track_3p_to_4p_index and tracks_xy.Track_3p_to_4p_index:
                # Only promote 4p candidates attached to the selected best 3p tracks.
                if best_track_xy_ind in tracks_xy.Track_3p_to_4p_index and best_track_xz_ind in tracks_xz.Track_3p_to_4p_index:
                    track_3p_of_4p_idx_xy = tracks_xy.Track_3p_to_4p_index.index(best_track_xy_ind)
                    track_3p_of_4p_idx_xz = tracks_xz.Track_3p_to_4p_index.index(best_track_xz_ind)

                    best_idx_xy = 0
                    best_track_4p_is_texp_null_xy = 1
                    if track_3p_of_4p_idx_xy < len(cluster_c4_texp_xy):
                        for k_idx, texp in enumerate(cluster_c4_texp_xy[track_3p_of_4p_idx_xy]):
                            if texp > 0:
                                best_track_4p_is_texp_null_xy = 0
                                best_idx_xy = k_idx
                                break
                    track_4p_idx_xy = best_idx_xy

                    best_idx_xz = 0
                    best_track_4p_is_texp_null_xz = 1
                    if track_3p_of_4p_idx_xz < len(cluster_c4_texp_xz):
                        for k_idx, texp in enumerate(cluster_c4_texp_xz[track_3p_of_4p_idx_xz]):
                            if texp > 0:
                                best_track_4p_is_texp_null_xz = 0
                                best_idx_xz = k_idx
                                break
                    track_4p_idx_xz = best_idx_xz

                    if (
                        track_3p_of_4p_idx_xy < len(tracks_xy.chiSquares_4p)
                        and track_3p_of_4p_idx_xz < len(tracks_xz.chiSquares_4p)
                        and track_4p_idx_xy < len(tracks_xy.chiSquares_4p[track_3p_of_4p_idx_xy])
                        and track_4p_idx_xz < len(tracks_xz.chiSquares_4p[track_3p_of_4p_idx_xz])
                    ):
                        best_track_4p_chi_xy = tracks_xy.chiSquares_4p[track_3p_of_4p_idx_xy][track_4p_idx_xy]
                        best_track_4p_chi_xz = tracks_xz.chiSquares_4p[track_3p_of_4p_idx_xz][track_4p_idx_xz]

                    if (
                        track_3p_of_4p_idx_xy < len(tracks_xy.ScatteringAngles)
                        and track_3p_of_4p_idx_xz < len(tracks_xz.ScatteringAngles)
                        and track_4p_idx_xy < len(tracks_xy.ScatteringAngles[track_3p_of_4p_idx_xy])
                        and track_4p_idx_xz < len(tracks_xz.ScatteringAngles[track_3p_of_4p_idx_xz])
                    ):
                        best_scattering_angle_xy = tracks_xy.ScatteringAngles[track_3p_of_4p_idx_xy][track_4p_idx_xy]
                        best_scattering_angle_xz = tracks_xz.ScatteringAngles[track_3p_of_4p_idx_xz][track_4p_idx_xz]

                    if (
                        track_3p_of_4p_idx_xy < len(tracks_xy.slope_4p)
                        and track_3p_of_4p_idx_xz < len(tracks_xz.slope_4p)
                        and track_4p_idx_xy < len(tracks_xy.slope_4p[track_3p_of_4p_idx_xy])
                        and track_4p_idx_xz < len(tracks_xz.slope_4p[track_3p_of_4p_idx_xz])
                    ):
                        coordinates_4p = TrackAngularCoordinates(
                            tracks_xy.slope_4p[track_3p_of_4p_idx_xy][track_4p_idx_xy],
                            tracks_xz.slope_4p[track_3p_of_4p_idx_xz][track_4p_idx_xz],
                            x_pos[0],
                            x_pos[3],
                        )
                        theta_4p, phi_4p = coordinates_4p
                        n_good_tracks_4p += 1

            event_record = {
                # Event-level payload kept close to original C++ tree naming.
                "Run": run,

                "Nclusters_Z1": nclusters_z1,
                "Nclusters_Z2": nclusters_z2,
                "Nclusters_Z3": nclusters_z3,
                "Nclusters_Z4": nclusters_z4,
                "Nclusters_Y1": nclusters_y1,
                "Nclusters_Y2": nclusters_y2,
                "Nclusters_Y3": nclusters_y3,
                "Nclusters_Y4": nclusters_y4,

                "ClusterSize_Z1": results_p1x.ClustersSize,
                "ClusterSize_Z2": results_p2x.ClustersSize,
                "ClusterSize_Z3": results_p3x.ClustersSize,
                "ClusterSize_Z4": results_p4x.ClustersSize,
                "ClusterZ1_Texp": results_p1x.TimeExpansions,
                "ClusterZ2_Texp": results_p2x.TimeExpansions,
                "ClusterZ3_Texp": results_p3x.TimeExpansions,
                "ClusterZ4_Texp": results_p4x.TimeExpansions,
                "ClusterEnergy_Z1": results_p1x.ClustersEnergy,
                "ClusterEnergy_Z2": results_p2x.ClustersEnergy,
                "ClusterEnergy_Z3": results_p3x.ClustersEnergy,
                "ClusterEnergy_Z4": results_p4x.ClustersEnergy,
                "ClusterPosition_Z1": results_p1x.ClustersPositions,
                "ClusterPosition_Z2": results_p2x.ClustersPositions,
                "ClusterPosition_Z3": results_p3x.ClustersPositions,
                "ClusterPosition_Z4": results_p4x.ClustersPositions,


                "ClusterSize_Y1": results_p1y.ClustersSize,
                "ClusterSize_Y2": results_p2y.ClustersSize,
                "ClusterSize_Y3": results_p3y.ClustersSize,
                "ClusterSize_Y4": results_p4y.ClustersSize,
                "ClusterY1_Texp": results_p1y.TimeExpansions,
                "ClusterY2_Texp": results_p2y.TimeExpansions,
                "ClusterY3_Texp": results_p3y.TimeExpansions,
                "ClusterY4_Texp": results_p4y.TimeExpansions,
                "ClusterEnergy_Y1": results_p1y.ClustersEnergy,
                "ClusterEnergy_Y2": results_p2y.ClustersEnergy,
                "ClusterEnergy_Y3": results_p3y.ClustersEnergy,
                "ClusterEnergy_Y4": results_p4y.ClustersEnergy,
                "ClusterPosition_Y1": results_p1y.ClustersPositions,
                "ClusterPosition_Y2": results_p2y.ClustersPositions,
                "ClusterPosition_Y3": results_p3y.ClustersPositions,
                "ClusterPosition_Y4": results_p4y.ClustersPositions,

                "StripsEnergy_Z1": results_p1x.StripsEnergy,
                "StripsEnergy_Z2": results_p2x.StripsEnergy,
                "StripsEnergy_Z3": results_p3x.StripsEnergy,
                "StripsEnergy_Z4": results_p4x.StripsEnergy,
                "StripsEnergy_Y1": results_p1y.StripsEnergy,
                "StripsEnergy_Y2": results_p2y.StripsEnergy,
                "StripsEnergy_Y3": results_p3y.StripsEnergy,
                "StripsEnergy_Y4": results_p4y.StripsEnergy,
                "StripsPosition_Z1": results_p1x.StripsPositions,
                "StripsPosition_Z2": results_p2x.StripsPositions,
                "StripsPosition_Z3": results_p3x.StripsPositions,
                "StripsPosition_Z4": results_p4x.StripsPositions,
                "StripsPosition_Y1": results_p1y.StripsPositions,
                "StripsPosition_Y2": results_p2y.StripsPositions,
                "StripsPosition_Y3": results_p3y.StripsPositions,
                "StripsPosition_Y4": results_p4y.StripsPositions,
                "StripsID_Z1": results_p1x.StripsID,
                "StripsID_Z2": results_p2x.StripsID,
                "StripsID_Z3": results_p3x.StripsID,
                "StripsID_Z4": results_p4x.StripsID,
                "StripsID_Y1": results_p1y.StripsID,
                "StripsID_Y2": results_p2y.StripsID,
                "StripsID_Y3": results_p3y.StripsID,
                "StripsID_Y4": results_p4y.StripsID,

                # Tracking branches
                "Ntracks_3p_xz": ntracks_3p_xz,
                "Ntracks_3p_xy": ntracks_3p_xy,
                "Intercept_3p_xz": tracks_xz.intercepts_3p,
                "Slope_3p_xz": tracks_xz.slopes_3p,
                "chiSquare_3p_xz": tracks_xz.chiSquares_3p,
                "Intercept_3p_xy": tracks_xy.intercepts_3p,
                "Slope_3p_xy": tracks_xy.slopes_3p,
                "chiSquare_3p_xy": tracks_xy.chiSquares_3p,
                "TrackCluster_z1_index": tracks_xz.cluster_index_1,
                "TrackCluster_z2_index": tracks_xz.cluster_index_2,
                "TrackCluster_z3_index": tracks_xz.cluster_index_3,
                "TrackCluster_y1_index": tracks_xy.cluster_index_1,
                "TrackCluster_y2_index": tracks_xy.cluster_index_2,
                "TrackCluster_y3_index": tracks_xy.cluster_index_3,

                "Residue_Track3p_z1": tracks_xz.residue_c1,
                "Residue_Track3p_z2": tracks_xz.residue_c2,
                "Residue_Track3p_z3": tracks_xz.residue_c3,
                "Residue_Track3p_y1": tracks_xy.residue_c1,
                "Residue_Track3p_y2": tracks_xy.residue_c2,
                "Residue_Track3p_y3": tracks_xy.residue_c3,
                "TrackEnergy_3p_xy": tracks_xy.TrackEnergy_3p,
                "TrackEnergy_3p_xz": tracks_xz.TrackEnergy_3p,
                "Plane4th_isIntercepted_xz": tracks_xz.Plane4th_isIntercepted,
                "Plane4th_isIntercepted_xy": tracks_xy.Plane4th_isIntercepted,
                "BestChi_xy_index": tracks_xy.BestChi_index,
                "BestEnergy_xy_index": tracks_xy.BestEnergy_index,
                "BestChi_xz_index": tracks_xz.BestChi_index,
                "BestEnergy_xz_index": tracks_xz.BestEnergy_index,
                "BestChi_xy": tracks_xy.BestChi,
                "BestEnergy_xy": tracks_xy.BestEnergy,
                "BestChi_xz": tracks_xz.BestChi,
                "BestEnergy_xz": tracks_xz.BestEnergy,
                "ExpectedPosition_OnPlane4th_xy": tracks_xy.ExpectedPosition_OnPlane4th,
                "ExpectedPosition_OnPlane4th_xz": tracks_xz.ExpectedPosition_OnPlane4th,

                "Intercept_4p_xz": tracks_xz.intercept_4p,
                "Slope_4p_xz": tracks_xz.slope_4p,
                "chiSquare_4p_xz": tracks_xz.chiSquares_4p,
                "displacement_p4_xz": tracks_xz.displacement_p4,
                "Intercept_4p_xy": tracks_xy.intercept_4p,
                "Slope_4p_xy": tracks_xy.slope_4p,
                "chiSquare_4p_xy": tracks_xy.chiSquares_4p,
                "displacement_p4_xy": tracks_xy.displacement_p4,
                "cluster_c4_index_xz": tracks_xz.cluster_indices_4,
                "cluster_c4_index_xy": tracks_xy.cluster_indices_4,
                "ScatteringAngle_xz": tracks_xz.ScatteringAngles,
                "ScatteringAngle_xy": tracks_xy.ScatteringAngles,

                "isInTrack_3p_clZ1": tracks_xz.IsInTrack_clusters1,
                "isInTrack_3p_clZ2": tracks_xz.IsInTrack_clusters2,
                "isInTrack_3p_clZ3": tracks_xz.IsInTrack_clusters3,
                "isInTrack_3p_clY1": tracks_xy.IsInTrack_clusters1,
                "isInTrack_3p_clY2": tracks_xy.IsInTrack_clusters2,   
                "isInTrack_3p_clY3": tracks_xy.IsInTrack_clusters3,
	            "isInTrack_4p_clZ1": tracks_xz.IsInTrack_clusters1_4p,
	            "isInTrack_4p_clZ2": tracks_xz.IsInTrack_clusters2_4p,
	            "isInTrack_4p_clZ3": tracks_xz.IsInTrack_clusters3_4p,
	            "isInTrack_4p_clY1": tracks_xy.IsInTrack_clusters1_4p,
	            "isInTrack_4p_clY2": tracks_xy.IsInTrack_clusters2_4p,
	            "isInTrack_4p_clY3": tracks_xy.IsInTrack_clusters3_4p,

                # BEST TRACKS
                "Theta_3p": theta_3p,
                "Theta_4p": theta_4p,
                "Phi_3p": phi_3p,
                "Phi_4p": phi_4p,
    
                "BestTrack_3p_xy_index": best_track_xy_ind,
                "BestTrack_3p_xz_index": best_track_xz_ind,
                "Track_3p_of_4p_index_xy": track_3p_of_4p_idx_xy,
                "Track_3p_of_4p_index_xz": track_3p_of_4p_idx_xz,
                "Track_4p_index_xy": track_4p_idx_xy,
                "Track_4p_index_xz": track_4p_idx_xz,

                "BestTrack_3p_ChiSquare_xy": best_track_3p_chi_xy,
                "BestTrack_3p_ChiSquare_xz": best_track_3p_chi_xz,
                "BestTrack_4p_ChiSquare_xy": best_track_4p_chi_xy,
                "BestTrack_4p_ChiSquare_xz": best_track_4p_chi_xz,
                "BestTracks_ScatteringAngle_xy": best_scattering_angle_xy,
                "BestTracks_ScatteringAngle_xz": best_scattering_angle_xz,
                "Best_track_4p_isTexpNULL_xy": best_track_4p_is_texp_null_xy,
                "Best_track_4p_isTexpNULL_xz": best_track_4p_is_texp_null_xz,

                "timestamp": timestamp,
                "WorkingPoint": int(working_point),
                "Temperature": temperature,
                "TriggerRate": trigger_rate,

                "TriggerMaskChannels": trigger_mask_channels,
                "TriggerMaskStrips": trigger_mask_strips,
                "TriggerMaskSize": trigger_mask_size,

                #only missing branches with respect to the C++ code are the "isBestTrack_3p_xy" and "isBestTrack_3p_xz" flags, but they are redundant since we have the indices of the best tracks, so we can easily derive them in the analysis if needed.

            }

            if event_keys is None:
                event_keys = list(event_record.keys())
                event_columns_chunk = {key: [] for key in event_keys}

            fill_start = time.time()
            for key in event_keys:
                event_columns_chunk[key].append(event_record.get(key))
            chunk_events += 1
            root_event_fill_elapsed += time.time() - fill_start

            if chunk_events >= max(1, root_chunk_size):
                flush_root_chunk()

            if progress_every > 0 and ev % progress_every == 0:
                elapsed = max(1e-9, time.time() - start_wall_time)
                rate = ev / elapsed
                print(
                    f"[progress] run={run} events={ev} elapsed={elapsed/60.0:.1f}m "
                    f"rate={rate:.1f} ev/s tracks3p_events={n_events_with_3p} "
                    f"tracks4p_events={n_events_with_4p}",
                    flush=True,
                )

        flush_root_chunk()

    if analyzed_nested_keys_seen:
        preview = ", ".join(sorted(analyzed_nested_keys_seen)[:8])
        if len(analyzed_nested_keys_seen) > 8:
            preview += ", ..."
        print(
            "[progress] Encoded nested event branches for ROOT compatibility: "
            f"{preview}",
            flush=True,
        )

    run_duration_min = 0.0
    if first_timestamp is not None and last_timestamp is not None:
        run_duration_min = max(0.0, (last_timestamp - first_timestamp) / 60.0)

    mean_cluster_energy_z1, rms_cluster_energy_z1 = _mean_rms(cluster_energy_acc["Z1"])
    mean_cluster_energy_z2, rms_cluster_energy_z2 = _mean_rms(cluster_energy_acc["Z2"])
    mean_cluster_energy_z3, rms_cluster_energy_z3 = _mean_rms(cluster_energy_acc["Z3"])
    mean_cluster_energy_z4, rms_cluster_energy_z4 = _mean_rms(cluster_energy_acc["Z4"])

    mean_cluster_energy_y1, rms_cluster_energy_y1 = _mean_rms(cluster_energy_acc["Y1"])
    mean_cluster_energy_y2, rms_cluster_energy_y2 = _mean_rms(cluster_energy_acc["Y2"])
    mean_cluster_energy_y3, rms_cluster_energy_y3 = _mean_rms(cluster_energy_acc["Y3"])
    mean_cluster_energy_y4, rms_cluster_energy_y4 = _mean_rms(cluster_energy_acc["Y4"])

    mean_nclusters_z1, rms_nclusters_z1 = _mean_rms(ncluster_acc["Z1"])
    mean_nclusters_z2, rms_nclusters_z2 = _mean_rms(ncluster_acc["Z2"])
    mean_nclusters_z3, rms_nclusters_z3 = _mean_rms(ncluster_acc["Z3"])
    mean_nclusters_z4, rms_nclusters_z4 = _mean_rms(ncluster_acc["Z4"])

    mean_nclusters_y1, rms_nclusters_y1 = _mean_rms(ncluster_acc["Y1"])
    mean_nclusters_y2, rms_nclusters_y2 = _mean_rms(ncluster_acc["Y2"])
    mean_nclusters_y3, rms_nclusters_y3 = _mean_rms(ncluster_acc["Y3"])
    mean_nclusters_y4, rms_nclusters_y4 = _mean_rms(ncluster_acc["Y4"])

    summary = {
        # Run-level aggregates: monitoring counters, mean/RMS observables, and config cuts.
        "Run": run,
        "Nevents": ev,
        "boards_OnePhes": boards_onephes,
        "IsOnePhe_aCopy": boards_is1phe_copy,
        "WorkingPoint": int(working_point),
        "Temperature": temperature,
        "TriggerRate": trigger_rate,
        "Nev_withAtrack3p": float(n_events_with_3p),
        "Nev_withAtrack3p_xy": float(n_events_with_3p_xy),
        "Nev_withAtrack3p_xz": float(n_events_with_3p_xz),
        "Nev_withAtrack4p": float(n_events_with_4p),
        "Ntracks_xy_3p": float(n_tracks_xy_3p),
        "Ntracks_xz_3p": float(n_tracks_xz_3p),
        "Ntracks_3p": float(n_tracks_3p),
        "Ntracks_xy_4p": float(n_tracks_xy_4p),
        "Ntracks_xz_4p": float(n_tracks_xz_4p),
        "Ntracks_4p": float(n_tracks_4p),
        "Nev_withAcluster_Z1": float(n_events_with_x1_cl),
        "Nev_withAcluster_Z2": float(n_events_with_x2_cl),
        "Nev_withAcluster_Z3": float(n_events_with_x3_cl),
        "Nev_withAcluster_Z4": float(n_events_with_x4_cl),
        "Nev_withAcluster_Y1": float(n_events_with_y1_cl),
        "Nev_withAcluster_Y2": float(n_events_with_y2_cl),
        "Nev_withAcluster_Y3": float(n_events_with_y3_cl),
        "Nev_withAcluster_Y4": float(n_events_with_y4_cl),
        "EnergyCut_clusterStrip": s1,
        "EnergyCut_singleStrip": s2,
        "EnergyCut_additionalStrip": s3,
        "proximity_cut_xz": proximity_cut_xz,
        "proximity_cut_xy": proximity_cut_xy,
        "RunDuration": run_duration_min,
        "Mean_clusterEnergy_Z1": mean_cluster_energy_z1,
        "Mean_clusterEnergy_Z2": mean_cluster_energy_z2,
        "Mean_clusterEnergy_Z3": mean_cluster_energy_z3,
        "Mean_clusterEnergy_Z4": mean_cluster_energy_z4,
        "RMS_clusterEnergy_Z1": rms_cluster_energy_z1,
        "RMS_clusterEnergy_Z2": rms_cluster_energy_z2,
        "RMS_clusterEnergy_Z3": rms_cluster_energy_z3,
        "RMS_clusterEnergy_Z4": rms_cluster_energy_z4,
        "Mean_clusterEnergy_Y1": mean_cluster_energy_y1,
        "Mean_clusterEnergy_Y2": mean_cluster_energy_y2,
        "Mean_clusterEnergy_Y3": mean_cluster_energy_y3,
        "Mean_clusterEnergy_Y4": mean_cluster_energy_y4,
        "RMS_clusterEnergy_Y1": rms_cluster_energy_y1,
        "RMS_clusterEnergy_Y2": rms_cluster_energy_y2,
        "RMS_clusterEnergy_Y3": rms_cluster_energy_y3,
        "RMS_clusterEnergy_Y4": rms_cluster_energy_y4,
        "Mean_Nclusters_Z1": mean_nclusters_z1,
        "RMS_Nclusters_Z1": rms_nclusters_z1,
        "Mean_Nclusters_Z2": mean_nclusters_z2,
        "RMS_Nclusters_Z2": rms_nclusters_z2,
        "Mean_Nclusters_Z3": mean_nclusters_z3,
        "RMS_Nclusters_Z3": rms_nclusters_z3,
        "Mean_Nclusters_Z4": mean_nclusters_z4,
        "RMS_Nclusters_Z4": rms_nclusters_z4,
        "Mean_Nclusters_Y1": mean_nclusters_y1,
        "RMS_Nclusters_Y1": rms_nclusters_y1,
        "Mean_Nclusters_Y2": mean_nclusters_y2,
        "RMS_Nclusters_Y2": rms_nclusters_y2,
        "Mean_Nclusters_Y3": mean_nclusters_y3,
        "RMS_Nclusters_Y3": rms_nclusters_y3,
        "Mean_Nclusters_Y4": mean_nclusters_y4,
        "RMS_Nclusters_Y4": rms_nclusters_y4,
        "NGoodTracks3p": n_good_tracks_3p,
        "NGoodTracks4p": n_good_tracks_4p,
        "analyzed_root_file": str(analyzed_root_target),
        "run_info_root_file": str(run_info_root_target),
    }

    event_loop_elapsed = max(1e-9, time.time() - start_wall_time)

    summary_output_start = time.time()
    with mini_summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    summary_output_elapsed = time.time() - summary_output_start

    run_info_start = time.time()
    run_info_payload, run_info_nested_keys = _build_root_payload(
        {k: [v] for k, v in summary.items() if not isinstance(v, str)},
        np,
        ak,
    )
    if not run_info_payload:
        run_info_payload["Run"] = np.asarray([run], dtype=np.int64)

    with uproot.recreate(run_info_root_target) as run_info_file:
        run_info_file["Run_info"] = run_info_payload

    root_run_info_elapsed = time.time() - run_info_start

    if run_info_nested_keys:
        print(
            "[progress] Encoded nested Run_info branches for ROOT compatibility: "
            + ", ".join(run_info_nested_keys),
            flush=True,
        )

    analyzed_root = analyzed_root_target
    run_info_root = run_info_root_target
    root_fill_elapsed = root_event_fill_elapsed + root_flush_elapsed + root_run_info_elapsed

    elapsed_total = max(1e-9, time.time() - total_start_wall_time)
    json_output_elapsed = summary_output_elapsed
    output_production_elapsed = json_output_elapsed + root_fill_elapsed
    reconstruction_core_elapsed = max(0.0, elapsed_total - output_production_elapsed)

    summary["EventLoopWallTimeSeconds"] = event_loop_elapsed
    summary["JsonOutputWallTimeSeconds"] = json_output_elapsed
    summary["RootEventFillWallTimeSeconds"] = root_event_fill_elapsed
    summary["RootFlushWallTimeSeconds"] = root_flush_elapsed
    summary["RootRunInfoWallTimeSeconds"] = root_run_info_elapsed
    summary["RootFillWallTimeSeconds"] = root_fill_elapsed
    summary["OutputProductionWallTimeSeconds"] = output_production_elapsed
    summary["ReconstructionCoreWallTimeSeconds"] = reconstruction_core_elapsed
    summary["ProcessingWallTimeSeconds"] = elapsed_total
    summary["ReconstructionRateEventsPerSecond"] = (
        ev / reconstruction_core_elapsed if ev > 0 and reconstruction_core_elapsed > 0 else 0.0
    )
    summary["ProcessingRateEventsPerSecond"] = ev / elapsed_total if ev > 0 else 0.0

    with mini_summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(f"Number of events: {ev}")
    print(f"[progress] Reconstruction core wall time: {reconstruction_core_elapsed:.2f} s", flush=True)
    print(f"[progress] Summary JSON output wall time: {json_output_elapsed:.2f} s", flush=True)
    print(f"[progress] ROOT event fill wall time: {root_event_fill_elapsed:.2f} s", flush=True)
    print(f"[progress] ROOT flush wall time: {root_flush_elapsed:.2f} s", flush=True)
    print(f"[progress] ROOT run-info wall time: {root_run_info_elapsed:.2f} s", flush=True)
    print(f"[progress] ROOT fill wall time: {root_fill_elapsed:.2f} s", flush=True)
    print(f"[progress] Output production wall time: {output_production_elapsed:.2f} s", flush=True)
    print(f"[progress] Total wall time: {elapsed_total:.2f} s", flush=True)
    if ev > 0:
        print(f"[progress] Reconstruction core rate: {summary['ReconstructionRateEventsPerSecond']:.1f} ev/s", flush=True)
        print(f"[progress] Average processing rate: {ev / elapsed_total:.1f} ev/s", flush=True)
    print(f"RUN {run} COMPLETED. Find your data in ---> {analyzed_root}")
    print(f"Find your minitree in ---> {mini_summary_json}")
    print(f"Find your ROOT minitree in ---> {run_info_root}")

    return analyzed_root, run_info_root


def parse_args(config_defaults: dict | None = None) -> argparse.Namespace:
    if config_defaults is None:
        config_defaults = get_reco_config()
    parser = argparse.ArgumentParser(
        description=(
            "Pythonized MURAVES reconstruction entrypoint for 4_MainRecSof (ROOT-only). "
            "Writes ROOT outputs directly from in-memory reconstruction payloads."
        )
    )
    parser.add_argument("color", type=str, help="Detector color: ROSSO, NERO, or BLU")
    parser.add_argument("run", type=int, help="Run number")
    parser.add_argument("end_run", nargs="?", default=None, help="Kept for CLI compatibility; ignored")
    parser.add_argument(
        "--output-base",
        type=Path,
        default=_resolve_default_output_base(),
        help="Base folder that contains PARSED/ PEDESTAL/ and RECONSTRUCTED/",
    )
    parser.add_argument(
        "--raw-base",
        type=Path,
        default=_resolve_default_raw_base(config_defaults),
        help="Base RAW folder that contains <COLOR>/SLOWCONTROL_run<run>",
    )
    parser.add_argument(
        "--tracks-base",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="tracks_reconstruction base path (contains AncillaryFiles)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON override for reconstruction parameters.",
    )
    parser.add_argument(
        "--base-config",
        type=Path,
        default=None,
        help="Optional base JSON configuration for reconstruction parameters.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=int(config_defaults["reconstruction"]["progress_every_default"]),
        help="Print progress every N events (set 0 to disable periodic progress logs).",
    )
    parser.add_argument(
        "--root-chunk-size",
        type=int,
        default=int(config_defaults["reconstruction"]["root_chunk_size_default"]),
        help="Number of events per ROOT chunk extend (smaller uses less memory, larger can reduce overhead).",
    )
    return parser.parse_args()


def main() -> None:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=None)
    pre_parser.add_argument("--base-config", type=Path, default=None)
    pre_args, _ = pre_parser.parse_known_args()

    # For rootonly scripts, use standalone_reco_parameters.json by default
    config_path = pre_args.config
    if config_path is None:
        standalone_config_default = Path(__file__).parent / "standalone_reco_parameters.json"
        if standalone_config_default.exists():
            config_path = standalone_config_default

    preloaded_config = get_reco_config(config_path, pre_args.base_config)
    args = parse_args(preloaded_config)

    if args.config is not None or args.base_config is not None:
        set_runtime_config_path(args.config, args.base_config)
    
    # Load with the determined config path
    final_config_path = args.config if args.config is not None else config_path
    config = get_reco_config(final_config_path, args.base_config)
    color = args.color.upper()
    run_reconstruction(
        color=color,
        run=args.run,
        output_base=args.output_base,
        raw_base=args.raw_base,
        tracks_base=args.tracks_base,
        progress_every=args.progress_every,
        root_chunk_size=args.root_chunk_size,
        config=config,
    )


if __name__ == "__main__":
    main()
