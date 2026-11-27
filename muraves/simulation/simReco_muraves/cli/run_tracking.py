# simReco_muraves/cli/run_tracking.py

"""Phase II: ClusteredData to TrackedData ROOT output.

    muraves-simTrk <clustered_root_file_or_directory> [-o OUTPUT]
    python -m simReco_muraves.cli.run_tracking <clustered_root_file>

The output is written in scratch and copied to its destination
(simReco_muraves.cli.common). In a directory, the inputs are the files
holding ClusteredData, whatever their names.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from muraves_lib.file_handler import scratch_to_output
from muraves_lib.reco.reco_config import get_reco_config
from simReco_muraves.cli.common import (
    add_scratch_argument,
    checked_scratch_dir,
    prepare_output,
    print_skipped,
    select_by_type,
)
from simReco_muraves.detector import detector_for, tracking_geometry
from simReco_muraves.io.clustered_root_reader import load_clusters
from simReco_muraves.io.provenance_tree import attach_provenance
from simReco_muraves.io.tracking_root_writer import (
    TrackedEventRecord,
    build_tracked_event_record,
    write_tracked_root,
)
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


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="muraves-simTrk",
        description=(
            "Run the MURAVES tracking reconstruction on simulated "
            "clustered data, writing TrackedData ROOT output."
        ),
    )

    parser.add_argument(
        "input_path",
        type=Path,
        help=(
            "ClusteredData ROOT file, or a directory: then every file "
            "in it holding ClusteredData is tracked, the output next to "
            "its input."
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "Output ROOT file. Only valid for a single input file; "
            "defaults to the input name with _clustered replaced by "
            "_tracked."
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
    print("Tracking Configuration")
    print("==================================================")
    print("Geometry         = from each input's detector (shown per file)")
    print(f"SIGMA_Z          = {SIGMA_Z}")
    print(f"SIGMA_Y          = {SIGMA_Y}")
    print(f"PROXIMITY_CUT_XZ = {PROXIMITY_CUT_XZ}")
    print(f"PROXIMITY_CUT_XY = {PROXIMITY_CUT_XY}")
    print("==================================================")
    print()


def build_output_name(input_file: Path) -> Path:
    stem = input_file.stem

    if "_clustered" in stem:
        stem = stem.replace("_clustered", "_tracked")
    else:
        stem = f"{stem}_tracked"

    return input_file.with_name(stem + ".root")


def process_file(
    input_file: Path,
    *,
    output_file: Path | None = None,
    force: bool = False,
    detector: str | None = None,
    scratch_dir: Path | None = None,
) -> None:

    geometry = tracking_geometry(detector_for([input_file], detector))

    output_file = prepare_output(
        input_file,
        output_file,
        force=force,
        default_name=build_output_name,
    )

    print()
    print("--------------------------------------------------")
    print("Processing")
    print("--------------------------------------------------")
    print(f"Input : {input_file}")
    print(f"Output: {output_file}")
    print(f"Detector: {geometry.detector}  x_pos={geometry.x_pos}  z_add={geometry.z_add}")
    print()

    clusters = load_clusters(str(input_file))
    print(f"Clusters loaded : {len(clusters):,}")

    if not clusters:
        raise RuntimeError(f"No clusters loaded from {input_file}")

    tracking_events = build_tracking_events(clusters)
    print(f"Tracking events : {len(tracking_events):,}")

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

    if len(tracking_events) != len(results):
        raise RuntimeError(
            "Tracking event/result count mismatch: "
            f"events={len(tracking_events)}, results={len(results)}"
        )

    records: list[TrackedEventRecord] = [
        build_tracked_event_record(event, result)
        for event, result in zip(tracking_events, results)
    ]

    print(f"Tracked records : {len(records):,}")

    with scratch_to_output(output_file, scratch_dir) as scratch_file:
        write_tracked_root(str(scratch_file), records)

        attach_provenance(
            scratch_file,
            stage="tracking",
            input_path=input_file,
            parameters={
                **geometry.as_parameters(),
                "sigma_z": SIGMA_Z,
                "sigma_y": SIGMA_Y,
                "proximity_cut_xz": PROXIMITY_CUT_XZ,
                "proximity_cut_xy": PROXIMITY_CUT_XY,
                "events": len(tracking_events),
            },
            recorded_as=output_file,
        )

    print()
    print(f"Wrote: {output_file}")
    print()


def get_cluster_files(path: Path) -> list[Path]:
    """The files in a folder that hold ClusteredData (review point B6:
    by tree, not by name, so earlier outputs are never taken as input)."""
    selected, skipped = select_by_type(path, {"clustered"})
    print_skipped(skipped)
    return [file_path for file_path, _ in selected]


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

    cluster_files = get_cluster_files(input_path)
    print(f"Found {len(cluster_files):,} clustered ROOT files.")

    if not cluster_files:
        raise RuntimeError("No clustered ROOT files found.")

    for index, file_path in enumerate(cluster_files, start=1):
        print()
        print(f"[{index}/{len(cluster_files)}]")
        process_file(
            file_path,
            force=arguments.force,
            detector=arguments.detector,
            scratch_dir=scratch_dir,
        )

    print()
    print("==================================================")
    print("Tracking production finished.")
    print("==================================================")
    print()


if __name__ == "__main__":
    main()
