"""Golden-track selection (step 4 of the MURAVES tracks reconstruction).

Python port of AnalysisOfCluster_and_tracks4planes.C, adapted from the
"experimental compatibility" golden output of simReco-muraves
(https://github.com/basnyats1024/simReco-muraves).

For every run listed in the step-3 batch stamp it reads
``MURAVES_AnalyzedData_run<N>.root`` (tree ``AnalyzedData``) and keeps only the
*golden* events: a valid best 3-plane XZ track AND a valid best 4-plane XZ
track (``BestTrack_3p_ChiSquare_xz != -1`` and ``BestTrack_4p_ChiSquare_xz != -1``),
exactly as the C++ macro. For each golden event it writes one entry of the
``Tracks4ptree`` tree with the C++ branch names:

* track summary: Theta, Phi, scattering angles, 3p/4p chi squares;
* for each of the 8 planes (Z1..Z4, Y1..Y4) the cluster on the track: energy,
  position, size, Texp, max/min strip energy;
* the cluster multiplicity of each plane and the clusters NOT on the track;
* run information: Run, TriggerRate, RunDuration, WorkingPoint, Timestamp.

Planes 1-3 use the clusters of the best 3p track (``TrackCluster_<p>k_index``
at ``BestTrack_3p_<proj>_index``); plane 4 uses the cluster of the best 4p
extension (``BestTrack_4p_ClusterIndex_<proj>``, written by step 3). By
construction in step 3 the best 4p track is attached to the best 3p track,
so all 4 clusters belong to the same track.

Nothing is recomputed: every value is copied from the step-3 output.
"""

from __future__ import annotations

import argparse
import logging
from functools import partial
from multiprocessing import Pool
from pathlib import Path

import awkward as ak
import numpy as np
import uproot

from muraves_lib import file_handler
from muraves_lib.reco.golden_selector import MISSING, is_golden

logger = logging.getLogger(__name__)

INPUT_TREE = "AnalyzedData"
RUN_INFO_TREE = "Run_info"
OUTPUT_TREE = "Tracks4ptree"

PLANES = ("Z1", "Z2", "Z3", "Z4", "Y1", "Y2", "Y3", "Y4")
PLANES_Z = ("Z1", "Z2", "Z3", "Z4")
PLANES_Y = ("Y1", "Y2", "Y3", "Y4")


# ---------------------------------------------------------------------------
# Output schema. Names and order follow the C++ Tracks4ptree (and the
# simReco-muraves experimental schema), including the historical
# "ClusterMultriplicity" spelling, so existing analysis macros keep working.
# ---------------------------------------------------------------------------
def build_output_schema() -> dict[str, str]:
    schema: dict[str, str] = {}
    for name in (
        "Phi", "Theta", "Scattering_xy", "Scattering_xz",
        "ChiSquare_xz", "ChiSquare_xy", "ChiSquare_3p_xz", "ChiSquare_3p_xy",
    ):
        schema[name] = "float64"
    for p in PLANES:
        schema[f"TrackClusterMaxStripEnergy_{p}"] = "float64"
        schema[f"TrackClusterMinStripEnergy_{p}"] = "float64"
    for p in PLANES_Z:
        schema[f"TrackClusterEnergy_{p}"] = "float64"
        schema[f"TrackClusterPosition_{p}"] = "float64"
        schema[f"TrackClusterSize_{p}"] = "int64"
    for p in PLANES_Y:
        schema[f"TrackClusterEnergy_{p}"] = "float64"
    for p in PLANES:
        schema[f"TrackClusterExp_{p}"] = "float64"
    for p in PLANES_Y:
        schema[f"TrackClusterPosition_{p}"] = "float64"
        schema[f"TrackClusterSize_{p}"] = "int64"
    for p in PLANES:
        schema[f"ClusterMultriplicity_{p}"] = "int64"
    for p in PLANES:
        schema[f"NonTrackClusterEnergy_{p}"] = "var * float64"
    for p in PLANES:
        schema[f"NonTrackClusterSize_{p}"] = "var * int64"
    for p in PLANES:
        schema[f"NonTrackClusterPosition_{p}"] = "var * float64"
    schema["Run"] = "int64"
    schema["TriggerRate"] = "float64"
    schema["RunDuration"] = "float64"
    schema["WorkingPoint"] = "int64"
    schema["Timestamp"] = "float64"
    return schema


def _input_branches() -> list[str]:
    branches = [
        "Run", "TriggerRate", "WorkingPoint", "timestamp",
        "Theta_4p", "Phi_4p",
        "BestTrack_3p_xz_index", "BestTrack_3p_xy_index",
        "BestTrack_3p_ChiSquare_xz", "BestTrack_3p_ChiSquare_xy",
        "BestTrack_4p_ChiSquare_xz", "BestTrack_4p_ChiSquare_xy",
        "BestTracks_ScatteringAngle_xz", "BestTracks_ScatteringAngle_xy",
        "BestTrack_4p_ClusterIndex_xz", "BestTrack_4p_ClusterIndex_xy",
    ]
    for p in PLANES:
        branches += [
            f"Nclusters_{p}", f"ClusterEnergy_{p}", f"ClusterPosition_{p}",
            f"ClusterSize_{p}", f"Cluster{p}_Texp", f"StripsEnergy_{p}",
        ]
    for proj in ("z", "y"):
        branches += [f"TrackCluster_{proj}{k}_index" for k in (1, 2, 3)]
    return branches


# ---------------------------------------------------------------------------
# Helpers (vectorised over events)
# ---------------------------------------------------------------------------
def _pick(jagged: ak.Array, index: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (jagged[i][index[i]], valid) for every event i.

    Uses the flat content + per-event offsets, so it works on plain numpy
    indices. Entries whose index is out of range get MISSING and valid=False.
    """
    counts = ak.to_numpy(ak.num(jagged)).astype(np.int64)
    flat = ak.to_numpy(ak.flatten(jagged))
    starts = np.cumsum(counts) - counts
    index = np.asarray(index, dtype=np.int64)
    valid = (index >= 0) & (index < counts)
    out = np.full(len(counts), MISSING, dtype=flat.dtype)
    out[valid] = flat[starts[valid] + index[valid]]
    return out, valid


def _strip_extremes(strips_flat: ak.Array, sizes: ak.Array, selected: np.ndarray):
    """Max/min strip energy of the selected cluster.

    In the step-3 ROOT output ``StripsEnergy_<plane>`` is the per-event
    concatenation of every cluster's strips (cluster order = ClusterEnergy
    order, strips sorted by decreasing energy inside each cluster), so the
    selected cluster starts at the cumulative size of the clusters before it.
    """
    first = ak.to_numpy(ak.sum(sizes[ak.local_index(sizes) < selected], axis=1)).astype(np.int64)
    size, _ = _pick(sizes, selected)
    strip_max, _ = _pick(strips_flat, first)
    strip_min, _ = _pick(strips_flat, first + size - 1)
    return strip_max, strip_min


def _read_run_duration(analyzed_root: Path, run: int) -> float:
    run_info = analyzed_root.with_name(f"MURAVES_miniRunTree_run{run}.root")
    try:
        with uproot.open(run_info) as handle:
            return float(handle[RUN_INFO_TREE]["RunDuration"].array(library="np")[0])
    except Exception as exc:  # noqa: BLE001 - logged, not fatal for the selection
        logger.warning("RunDuration not available for run %s (%s): %s", run, run_info, exc)
        return float(MISSING)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------
def select_golden(events: ak.Array, run_duration: float) -> tuple[dict, dict[str, int]]:
    """Apply the golden gate and project the events onto the Tracks4ptree schema.

    Returns (columns, counters). ``counters`` contains the number of input,
    golden and inconsistent (dropped) events.
    """
    n_input = len(events)
    gate = is_golden(events["BestTrack_3p_ChiSquare_xz"], events["BestTrack_4p_ChiSquare_xz"])
    events = events[gate]
    n_gate = len(events)

    # Selected cluster index on each plane: planes 1-3 from the best 3p track,
    # plane 4 from the best 4p extension (stored as a scalar by step 3).
    best_3p = {
        "z": ak.to_numpy(events["BestTrack_3p_xz_index"]),
        "y": ak.to_numpy(events["BestTrack_3p_xy_index"]),
    }
    consistent = np.ones(n_gate, dtype=bool)
    cluster_index: dict[str, np.ndarray] = {}
    for p in PLANES:
        proj, k = p[0].lower(), p[1]
        if k == "4":
            value = ak.to_numpy(events[f"BestTrack_4p_ClusterIndex_x{proj}"]).astype(np.int64)
        else:
            value, ok = _pick(events[f"TrackCluster_{proj}{k}_index"], best_3p[proj])
            value = value.astype(np.int64)
            consistent &= ok
        n_clusters = ak.to_numpy(ak.num(events[f"ClusterEnergy_{p}"]))
        consistent &= (value >= 0) & (value < n_clusters)
        # Strip list must match the cluster sizes, otherwise max/min are meaningless.
        consistent &= ak.to_numpy(
            ak.num(events[f"StripsEnergy_{p}"]) == ak.sum(events[f"ClusterSize_{p}"], axis=1)
        )
        cluster_index[p] = value

    n_inconsistent = int((~consistent).sum())
    if n_inconsistent:
        logger.warning(
            "%d golden events dropped because their track/cluster indices are inconsistent.",
            n_inconsistent,
        )
    events = events[consistent]
    cluster_index = {p: v[consistent] for p, v in cluster_index.items()}

    columns: dict[str, object] = {
        "Phi": events["Phi_4p"],
        "Theta": events["Theta_4p"],
        "Scattering_xy": events["BestTracks_ScatteringAngle_xy"],
        "Scattering_xz": events["BestTracks_ScatteringAngle_xz"],
        "ChiSquare_xz": events["BestTrack_4p_ChiSquare_xz"],
        "ChiSquare_xy": events["BestTrack_4p_ChiSquare_xy"],
        "ChiSquare_3p_xz": events["BestTrack_3p_ChiSquare_xz"],
        "ChiSquare_3p_xy": events["BestTrack_3p_ChiSquare_xy"],
    }
    for p in PLANES:
        sel = cluster_index[p]
        energy = events[f"ClusterEnergy_{p}"]
        position = events[f"ClusterPosition_{p}"]
        size = events[f"ClusterSize_{p}"]
        not_track = ak.local_index(energy) != sel

        strip_max, strip_min = _strip_extremes(events[f"StripsEnergy_{p}"], size, sel)
        columns[f"TrackClusterMaxStripEnergy_{p}"] = strip_max
        columns[f"TrackClusterMinStripEnergy_{p}"] = strip_min
        columns[f"TrackClusterEnergy_{p}"] = _pick(energy, sel)[0]
        columns[f"TrackClusterPosition_{p}"] = _pick(position, sel)[0]
        columns[f"TrackClusterSize_{p}"] = _pick(size, sel)[0]
        columns[f"TrackClusterExp_{p}"] = _pick(events[f"Cluster{p}_Texp"], sel)[0]
        columns[f"ClusterMultriplicity_{p}"] = events[f"Nclusters_{p}"]
        columns[f"NonTrackClusterEnergy_{p}"] = energy[not_track]
        columns[f"NonTrackClusterSize_{p}"] = size[not_track]
        columns[f"NonTrackClusterPosition_{p}"] = position[not_track]

    n_out = len(events)
    columns["Run"] = events["Run"]
    columns["TriggerRate"] = events["TriggerRate"]
    columns["RunDuration"] = np.full(n_out, run_duration, dtype=np.float64)
    columns["WorkingPoint"] = events["WorkingPoint"]
    columns["Timestamp"] = events["timestamp"]

    # Cast to the schema types and order.
    schema = build_output_schema()
    ordered: dict[str, object] = {}
    for name, typ in schema.items():
        if typ.startswith("var"):
            ordered[name] = ak.values_astype(columns[name], typ.split("* ")[1])
        else:
            ordered[name] = ak.to_numpy(ak.values_astype(columns[name], typ))

    counters = {
        "input": n_input,
        "gate": n_gate,
        "golden": n_out,
        "inconsistent": n_inconsistent,
    }
    return ordered, counters


def _write_tree(path: Path, columns: dict) -> None:
    schema = build_output_schema()
    with uproot.recreate(path) as handle:
        # Typed tree first, so a run without golden events still has an
        # (empty) Tracks4ptree that downstream code can open.
        tree = handle.mktree(OUTPUT_TREE, dict(schema))
        if len(columns["Run"]) > 0:
            tree.extend(columns)


def _copy_metadata(source: Path, destination: Path, counters: dict[str, int]) -> None:
    """Propagate step-3 provenance (git/config METADATA) and add golden counters."""
    try:
        from muraves_lib import root_wrapper

        metadata = root_wrapper.load_root_metadata(source) or {}
        metadata["golden_selection"] = {"source_file": str(source), **counters}
        root_wrapper.add_metadata_to_root(destination, None, prebuilt_metadata=metadata)
    except Exception as exc:  # noqa: BLE001 - metadata is informative only
        logger.warning("Could not write METADATA to %s: %s", destination, exc)


# ---------------------------------------------------------------------------
# Per-run and batch drivers
# ---------------------------------------------------------------------------
def golden_output_path(analyzed_root: Path, output_dir: Path) -> tuple[Path, int]:
    stem = analyzed_root.stem  # MURAVES_AnalyzedData_run<N>
    if "run" not in stem:
        raise ValueError(f"Unable to extract run number from {analyzed_root}")
    run = int(stem.split("run")[-1])
    return output_dir / f"Track4p_run{run}.root", run


def process_run(analyzed_root: str | Path, output_dir: Path, overwrite: bool) -> Path | None:
    analyzed_root = Path(analyzed_root)
    output_root, run = golden_output_path(analyzed_root, output_dir)

    if not overwrite and output_root.exists():
        logger.info("Output %s already exists. Skipping run %s.", output_root, run)
        return output_root

    if analyzed_root.suffix != ".root":
        logger.error("Run %s: golden selection needs the ROOT output of step 3, got %s", run, analyzed_root)
        return None
    try:
        with uproot.open(analyzed_root) as handle:
            if INPUT_TREE not in handle:
                logger.error("Run %s: tree %s not found in %s", run, INPUT_TREE, analyzed_root)
                return None
            tree = handle[INPUT_TREE]
            missing = [b for b in _input_branches() if b not in tree.keys()]
            if missing:
                logger.error(
                    "Run %s: input %s lacks branches %s (was it produced by an older step 3?)",
                    run, analyzed_root, ", ".join(missing),
                )
                return None
            events = tree.arrays(_input_branches(), library="ak")
    except Exception as exc:  # noqa: BLE001 - one broken run must not stop the batch
        logger.error("Run %s: cannot read %s: %s", run, analyzed_root, exc)
        return None

    run_duration = _read_run_duration(analyzed_root, run)
    columns, counters = select_golden(events, run_duration)

    output_root.parent.mkdir(parents=True, exist_ok=True)
    with file_handler.temp_to_output(output_root) as tmp_path:
        _write_tree(tmp_path, columns)
        _copy_metadata(analyzed_root, tmp_path, counters)

    if counters["golden"] == 0:
        logger.warning("Run %s: no golden events (%s). Empty %s written.", run, counters, OUTPUT_TREE)
    else:
        logger.info("Run %s: %s -> %s", run, counters, output_root)
    print(
        f"[golden] run={run} input={counters['input']} golden={counters['golden']} "
        f"inconsistent={counters['inconsistent']} -> {output_root}",
        flush=True,
    )
    return output_root


def _configure_logging(log_on_console: str, verbose: str, output_filename: Path) -> None:
    level = getattr(logging, verbose.upper())
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    if log_on_console == "True":
        logging.basicConfig(level=level, format=fmt)
        return
    log_file = Path("logs/GOLDEN_SELECTION") / output_filename.with_suffix(".log").name
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("", encoding="utf-8")
    logging.basicConfig(filename=log_file, level=level, format=fmt)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Golden-track selection: keep events with a valid 3-plane and 4-plane XZ "
        "track and write the Tracks4ptree for every run of a step-3 batch."
    )
    parser.add_argument("-i", "--input-filename", type=Path, required=True,
                        help="Step-3 batch stamp listing MURAVES_AnalyzedData_run<N>.root files.")
    parser.add_argument("-o", "--output-filename", type=Path, required=True,
                        help="Batch stamp to write; Track4p_run<N>.root files go in the same folder.")
    parser.add_argument("-th", "--num-threads", type=int, default=1)
    parser.add_argument("-l", "--log-on-console", default="False")
    parser.add_argument("-v", "--verbose", default="info")
    parser.add_argument("-ow", "--overwrite-outputs", default="True")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _configure_logging(args.log_on_console, args.verbose, args.output_filename)
    overwrite = str(args.overwrite_outputs).strip().lower() == "true"
    args.output_filename.parent.mkdir(parents=True, exist_ok=True)

    with args.input_filename.open("r", encoding="utf-8") as handle:
        inputs = [line.strip() for line in handle if line.strip()]

    worker = partial(process_run, output_dir=args.output_filename.parent, overwrite=overwrite)
    if inputs:
        with Pool(max(1, args.num_threads)) as pool:
            outputs = pool.map(worker, inputs)
    else:
        logger.info("No step-3 outputs listed in %s", args.input_filename)
        outputs = []

    produced = [str(o) for o in outputs if o is not None]
    failed = len(outputs) - len(produced)
    with file_handler.temp_to_output(args.output_filename) as tmp:
        Path(tmp).write_text("".join(f"{o}\n" for o in produced), encoding="utf-8")

    if failed:
        logger.error("%d run(s) of %s could not be processed, see log above.", failed, args.input_filename)
    print(f"Batch {args.output_filename.stem} completed: {len(produced)} run(s), {failed} failed.", flush=True)


if __name__ == "__main__":
    main()
