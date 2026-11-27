# simReco_muraves/cli/run_gTrks.py

"""Phase III: golden-track selection from ClusteredData or TrackedData.

    muraves-simGTrk <root_file_or_directory> [--input-type auto]
    python -m simReco_muraves.cli.run_gTrks <root_file>

The input type is detected from the tree present in the file. Passing
--input-type asserts the expected type rather than overriding
detection: for a file, a mismatch is an error, not a silent
reinterpretation; in a directory, it selects the files of that type.

The output is written in scratch and copied to its destination
(simReco_muraves.cli.common).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uproot

from muraves_lib.file_handler import scratch_to_output
from muraves_lib.reco.reco_config import get_reco_config
from simReco_muraves.cli.common import (
    add_scratch_argument,
    checked_scratch_dir,
    prepare_output,
    print_skipped,
    root_file_type,
    select_by_type,
)
from simReco_muraves.golden_tracking.production_pipeline import (
    run_golden_tracking_output,
)
from simReco_muraves.golden_tracking.tracked_pipeline import (
    run_golden_tracking_from_tracked,
)
from simReco_muraves.detector import detector_for, tracking_geometry
from simReco_muraves.io.clustered_root_reader import load_clusters
from simReco_muraves.io.provenance_tree import attach_provenance
from simReco_muraves.tracking.event_builder_adapter import (
    build_tracking_events,
)
from simReco_muraves.tracking.tracking_pipeline_adapter import (
    run_tracking_pipeline,
)


# Geometry: the simulated detector's entry in the shared configuration,
# for the detector recorded in the input's provenance (simReco_muraves.detector).


# ==========================================================
# Tracking parameters: from the shared reconstruction configuration
# (muraves_lib/configuration), computed as the data chain does.
# ==========================================================

_RECONSTRUCTION = get_reco_config(chain="simulation")["reconstruction"]

SIGMA_Z = float(_RECONSTRUCTION["sigma_z"])
SIGMA_Y = float(_RECONSTRUCTION["sigma_y"])

PROXIMITY_CUT_XZ = float(_RECONSTRUCTION["proximity_sigma_multiplier"]) * SIGMA_Z
PROXIMITY_CUT_XY = float(_RECONSTRUCTION["proximity_sigma_multiplier"]) * SIGMA_Y

TREE_NAME = "Tracks4ptree"

INPUT_TYPES = ("clustered", "tracked")

REQUIRED_BRANCHES = {
    "ProcessID",
    "EventID",
    "Theta",
    "Phi",
    "Scattering_xz",
    "Scattering_xy",
    "ChiSquare_xz",
    "ChiSquare_xy",
    "ChiSquare_3p_xz",
    "ChiSquare_3p_xy",
    "TrackClusterEnergy_Z1",
    "TrackClusterEnergy_Z4",
    "TrackClusterEnergy_Y1",
    "TrackClusterEnergy_Y4",
    "ClusterMultiplicity_Z1",
    "NonTrackClusterEnergy_Z1",
}


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="muraves-simGTrk",
        description=(
            "Produce simulated golden-track output from either "
            "ClusteredData (runs tracking) or TrackedData (reuses "
            "persisted tracking state)."
        ),
    )

    parser.add_argument(
        "input_path",
        type=Path,
        help="ClusteredData or TrackedData ROOT file, or a directory.",
    )

    parser.add_argument(
        "--input-type",
        choices=("auto", "clustered", "tracked"),
        default="auto",
        help=(
            "Expected input type. The default detects it from the "
            "file; naming a type asserts it and errors on mismatch. "
            "In a directory, only the files of that type are used."
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output ROOT file. Only valid for a single input file."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )

    add_scratch_argument(parser)

    parser.add_argument(
        "--detector",
        type=str.upper,
        default=None,
        help=(
            "Simulated detector, for inputs that record none. Normally "
            "taken from the input's provenance; if given, it must agree."
        ),
    )

    return parser.parse_args(argv)


def print_configuration() -> None:
    print()
    print("==================================================")
    print("Simulated Golden-Track Reconstruction")
    print("==================================================")
    print("Geometry         = from each input's detector (shown per file)")
    print(f"SIGMA_Z          = {SIGMA_Z}")
    print(f"SIGMA_Y          = {SIGMA_Y}")
    print(f"PROXIMITY_CUT_XZ = {PROXIMITY_CUT_XZ}")
    print(f"PROXIMITY_CUT_XY = {PROXIMITY_CUT_XY}")
    print(f"TREE_NAME        = {TREE_NAME}")
    print("==================================================")
    print()


def classify_input_file(path: Path) -> str:
    return root_file_type(path)


def resolve_input_type(path: Path, expected: str) -> str:
    """Detected type, checked against an explicitly requested one.

    A mismatch raises ValueError (review point B5: an exception the
    directory loop handles like any other, not SystemExit).
    """
    detected = classify_input_file(path)

    if expected == "auto":
        return detected

    if detected != expected:
        raise ValueError(
            f"--input-type {expected} was requested, but "
            f"{path.name} contains {detected} data."
        )

    return detected


def build_output_name(input_file: Path) -> Path:
    stem = input_file.stem

    for marker in ("_clustered", "_tracked"):
        if marker in stem:
            return input_file.with_name(
                stem.replace(marker, "_golden") + ".root"
            )

    return input_file.with_name(f"{stem}_golden.root")


def inspect_output(output_file: Path) -> None:
    with uproot.open(output_file) as root_file:
        tree = root_file[TREE_NAME]

        physical_branches = list(tree.keys())

        counter_branches = [
            name
            for name in physical_branches
            if name.startswith("nNonTrackCluster")
        ]

        logical_branches = [
            name
            for name in physical_branches
            if name not in counter_branches
        ]

        print()
        print("Golden ROOT output inspection")
        print("--------------------------------------------------")
        print(f"Tree              : {TREE_NAME}")
        print(f"Selected entries  : {tree.num_entries:,}")
        print(f"Logical branches  : {len(logical_branches)}")
        print(f"Counter branches  : {len(counter_branches)}")
        print(f"Physical branches : {len(physical_branches)}")

        missing = sorted(REQUIRED_BRANCHES - set(physical_branches))
        print(f"Missing required branches: {missing}")

        if missing:
            raise RuntimeError("Golden ROOT output is incomplete")

        if tree.num_entries > 0:
            entry_stop = min(10, tree.num_entries)

            process_ids = tree["ProcessID"].array(
                library="np",
                entry_stop=entry_stop,
            ).tolist()

            event_ids = tree["EventID"].array(
                library="np",
                entry_stop=entry_stop,
            ).tolist()

            print(f"First ProcessID values: {process_ids}")
            print(f"First EventID values  : {event_ids}")

        print("Simulated golden Tracks4ptree: OK")


def _prepare_output(
    input_file: Path,
    output_file: Path | None,
    force: bool,
) -> Path:
    return prepare_output(
        input_file,
        output_file,
        force=force,
        default_name=build_output_name,
    )


def output_collisions(input_files: list[Path]) -> dict[Path, list[Path]]:
    """Inputs whose default outputs coincide (review point B5):
    X_clustered_partN and X_tracked_partN both give X_golden_partN."""
    by_output: dict[Path, list[Path]] = {}

    for input_file in input_files:
        by_output.setdefault(build_output_name(input_file), []).append(input_file)

    return {
        output: inputs
        for output, inputs in sorted(by_output.items())
        if len(inputs) > 1
    }


def process_tracked_file(
    input_file: Path,
    *,
    output_file: Path | None = None,
    force: bool = False,
    detector: str | None = None,
    scratch_dir: Path | None = None,
) -> None:

    # No refit on this route: the detector is only checked and recorded.
    detector = detector_for([input_file], detector)
    output_file = _prepare_output(input_file, output_file, force)

    print()
    print("--------------------------------------------------")
    print("Processing tracked ROOT")
    print("--------------------------------------------------")
    print(f"Input : {input_file}")
    print(f"Output: {output_file}")

    with scratch_to_output(output_file, scratch_dir) as scratch_file:
        written_path = run_golden_tracking_from_tracked(
            tracked_root_file=input_file,
            output_file=scratch_file,
        )

        attach_provenance(
            written_path,
            stage="golden",
            input_path=input_file,
            parameters={
                "route": "tracked",
                "tree_name": TREE_NAME,
                "detector": detector,
            },
            recorded_as=output_file,
        )

        # Checked before the copy, so an incomplete file is never put in place.
        inspect_output(Path(written_path))

    print(f"Wrote: {output_file}")


def process_clustered_file(
    input_file: Path,
    *,
    output_file: Path | None = None,
    force: bool = False,
    detector: str | None = None,
    scratch_dir: Path | None = None,
) -> None:

    geometry = tracking_geometry(detector_for([input_file], detector))
    output_file = _prepare_output(input_file, output_file, force)

    print()
    print("--------------------------------------------------")
    print("Processing clustered ROOT")
    print("--------------------------------------------------")
    print(f"Input : {input_file}")
    print(f"Output: {output_file}")
    print(f"Detector: {geometry.detector}  x_pos={geometry.x_pos}  z_add={geometry.z_add}")

    clusters = load_clusters(str(input_file))
    print(f"Clusters loaded : {len(clusters):,}")

    if not clusters:
        raise RuntimeError(f"No clusters loaded from {input_file}")

    events = build_tracking_events(clusters)
    print(f"Tracking events : {len(events):,}")

    configuration = get_reco_config(chain="simulation")

    results = run_tracking_pipeline(
        clusters,
        x_pos=geometry.x_pos,
        z_add=geometry.z_add,
        y_add=geometry.y_add,
        sigma_z=SIGMA_Z,
        sigma_y=SIGMA_Y,
        proximity_cut_xz=PROXIMITY_CUT_XZ,
        proximity_cut_xy=PROXIMITY_CUT_XY,
        tracking_cfg=configuration["tracking"],
        strips_cfg=configuration["strips"],
    )

    print(f"Tracking results: {len(results):,}")

    if len(events) != len(results):
        raise RuntimeError(
            "Tracking event/result count mismatch: "
            f"events={len(events)}, results={len(results)}"
        )

    with scratch_to_output(output_file, scratch_dir) as scratch_file:
        written_path = run_golden_tracking_output(
            events=events,
            results=results,
            output_path=scratch_file,
            tree_name=TREE_NAME,
        )

        attach_provenance(
            written_path,
            stage="golden",
            input_path=input_file,
            parameters={
                "route": "clustered",
                "tree_name": TREE_NAME,
                **geometry.as_parameters(),
                "sigma_z": SIGMA_Z,
                "sigma_y": SIGMA_Y,
                "proximity_cut_xz": PROXIMITY_CUT_XZ,
                "proximity_cut_xy": PROXIMITY_CUT_XY,
            },
            recorded_as=output_file,
        )

        # Checked before the copy, so an incomplete file is never put in place.
        inspect_output(Path(written_path))

    print(f"Wrote: {output_file}")


def process_file(
    input_file: Path,
    *,
    expected_type: str = "auto",
    output_file: Path | None = None,
    force: bool = False,
    detector: str | None = None,
    scratch_dir: Path | None = None,
) -> None:

    file_type = resolve_input_type(input_file, expected_type)

    if file_type == "tracked":
        process_tracked_file(
            input_file,
            output_file=output_file,
            force=force,
            detector=detector,
            scratch_dir=scratch_dir,
        )
        return

    if file_type == "clustered":
        process_clustered_file(
            input_file,
            output_file=output_file,
            force=force,
            detector=detector,
            scratch_dir=scratch_dir,
        )
        return

    if file_type == "golden":
        raise RuntimeError("Input is already a Golden ROOT file")

    raise RuntimeError(f"Unknown ROOT format: {input_file}")


def get_input_files(path: Path, input_type: str = "auto") -> list[Path]:
    """The folder's inputs, by the tree they hold (review point B6):
    ClusteredData and TrackedData files, or only those of input_type.

    With auto, a folder holding the clustered and the tracked version
    of a chunk is refused, since both would give the same golden file
    (review point B5)."""
    wanted = INPUT_TYPES if input_type == "auto" else (input_type,)
    selected, skipped = select_by_type(path, wanted)
    print_skipped(skipped)
    files = [file_path for file_path, _ in selected]

    collisions = output_collisions(files)

    if collisions:
        lines = [
            f"  {output.name} <- {', '.join(i.name for i in inputs)}"
            for output, inputs in list(collisions.items())[:5]
        ]
        raise ValueError(
            f"{len(collisions)} golden output(s) would come from two "
            "inputs, e.g.\n" + "\n".join(lines) + "\n"
            "Choose one route with --input-type clustered or "
            "--input-type tracked."
        )

    return files


def main(argv: list[str] | None = None) -> None:
    try:
        _main(argv)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from None


def _main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)

    input_path = arguments.input_path.expanduser().resolve()

    if not input_path.exists():
        raise FileNotFoundError(input_path)

    scratch_dir = checked_scratch_dir(arguments.scratch_dir)

    print_configuration()

    if input_path.is_file():
        process_file(
            input_path,
            expected_type=arguments.input_type,
            output_file=arguments.output,
            force=arguments.force,
            detector=arguments.detector,
            scratch_dir=scratch_dir,
        )
        return

    if arguments.output is not None:
        raise SystemExit(
            "--output is only valid for a single input file."
        )

    input_files = get_input_files(input_path, arguments.input_type)
    print(f"Found {len(input_files):,} input ROOT files.")

    if not input_files:
        raise RuntimeError("No compatible ROOT files found")

    failures: list[tuple[Path, Exception]] = []

    for index, file_path in enumerate(input_files, start=1):
        print()
        print(f"[{index}/{len(input_files)}]")

        try:
            process_file(
                file_path,
                expected_type=arguments.input_type,
                force=arguments.force,
                detector=arguments.detector,
                scratch_dir=scratch_dir,
            )

        except Exception as error:
            failures.append((file_path, error))
            print(
                f"FAILED: {file_path}: "
                f"{type(error).__name__}: {error}"
            )

    print()
    print("==================================================")
    print("Golden tracking production finished")
    print("==================================================")
    print(f"Successful files: {len(input_files) - len(failures)}")
    print(f"Failed files    : {len(failures)}")

    if failures:
        print()
        print("Failures:")
        for file_path, error in failures:
            print(
                f"  {file_path}: "
                f"{type(error).__name__}: {error}"
            )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
