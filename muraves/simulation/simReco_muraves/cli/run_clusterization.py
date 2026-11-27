# simReco_muraves/cli/run_clusterization.py

"""Phase I: simulated hits to ClusteredData ROOT output.

    muraves-simCluster <hit_root_file> --detector NERO -o OUTPUT_DIR
    python -m simReco_muraves.cli.run_clusterization <hit_root_file> --detector NERO -o OUTPUT_DIR

The chunks are written to a scratch folder. At the end of the run, the
METADATA (with the run's totals) is added to each, and they are
copied to OUTPUT_DIR (review points A1 and A2 of PR #26). The run refuses to
start if OUTPUT_DIR already holds chunks of the same prefix, unless
--force, which replaces them: those this run does not rewrite are
removed (review point B2). If the run fails, no chunk of the prefix is
left in OUTPUT_DIR.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from muraves_lib.file_handler import (
    copy_into_place,
    make_output_dir,
    scratch_folder,
)
from simReco_muraves.cli.common import (
    add_scratch_argument,
    checked_scratch_dir,
)
from simReco_muraves.clustering.sim_clusterizer import (
    LandauPathDigitizer,
    PoissonDigitizer,
    SimClusterizer,
    aggregate_bar_hits,
    build_planes,
    cluster_collection_to_records,
)
from simReco_muraves.io.provenance_tree import (
    attach_provenance_to_many,
)
from simReco_muraves.io.root_reader import RootReader
from simReco_muraves.io.root_writer import RootWriter
from simReco_muraves.clustering.seeding import SEEDING_SCHEME
from simReco_muraves.detector import known_detectors, packaged_calibration_file
from simReco_muraves.clustering.conversion_factors import (
    digitization_setup,
    parse_run_range,
)


# Detector-response defaults. These reproduce the configuration used for
# the Phase I-III validation samples; change them only deliberately,
# since the cluster energy scale depends directly on PE_PER_MEV.
DEFAULT_PE_PER_MEV = 8.5
DEFAULT_RNG_SEED = 42
DEFAULT_CHUNK_SIZE = 100_000
DEFAULT_PROGRESS_EVERY = 25_000


def _run_range_argument(text: str):
    try:
        return parse_run_range(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from None


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="muraves-simCluster",
        description=(
            "Aggregate simulated Geant4 hits, digitize them and run "
            "the MURAVES clusterization, writing ClusteredData ROOT "
            "chunks."
        ),
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="ROOT file containing the simulated HitData tree.",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help=(
            "Directory for the ClusteredData chunks (required). "
            "Created if missing, group-writable."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Replace the chunks of the same prefix already in the output "
            "directory. Without it, the run refuses to start if there "
            "are any."
        ),
    )

    add_scratch_argument(parser)

    parser.add_argument(
        "--output-prefix",
        default=None,
        help=(
            "Chunk filename prefix (default: <input stem>_<detector>"
            "_clustered, with the run range added after the detector "
            "when --pe-per-cm-file is used)."
        ),
    )

    parser.add_argument(
        "--pe-per-mev",
        type=float,
        default=None,
        help=(
            "Energy method: One photoelectron yield per MeV for every plane "
            f"(default: {DEFAULT_PE_PER_MEV}). Cannot be combined "
            "with --pe-per-cm-file."
        ),
    )

    parser.add_argument(
        "--pe-per-cm-file",
        type=Path,
        nargs="?",
        const=packaged_calibration_file(),
        default=None,
        metavar="FILE",
        help=(
            "Path-length method: per-plane NPE/cm from a calibration file "
            "for --detector; without FILE, the calibration shipped in "
            "muraves_lib/configuration/simulation/. --run-range is "
            "optional; without it, the detector's fallback setting is "
            "used (NERO and BLU wp25_a, ROSSO wp25_b)."
        ),
    )

    parser.add_argument(
        "--detector",
        type=str.upper,
        choices=known_detectors(),
        required=True,
        help=(
            "Simulated detector (required). Recorded in each output's "
            "METADATA: the tracking and golden stages reconstruct with its geometry. "
            "With --pe-per-cm-file, also selects its calibration."
        ),
    )

    parser.add_argument(
        "--run-range",
        type=_run_range_argument,
        default=None,
        metavar="START-END",
        help=(
            "Run range whose calibration to use, e.g. 10061-11918 or a "
            "single run. Only with --pe-per-cm-file."
        ),
    )

    parser.add_argument(
        "--rng-seed",
        type=int,
        default=DEFAULT_RNG_SEED,
        help=(
            "Master seed for digitization and single-strip smearing "
            f"(default: {DEFAULT_RNG_SEED})."
        ),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=(
            "Clusters per output ROOT chunk; a chunk ends only between "
            "events, so it can hold one event's clusters more "
            f"(default: {DEFAULT_CHUNK_SIZE})."
        ),
    )

    parser.add_argument(
        "--progress-every",
        type=int,
        default=DEFAULT_PROGRESS_EVERY,
        help=(
            "Print progress every N events "
            f"(default: {DEFAULT_PROGRESS_EVERY})."
        ),
    )

    return parser.parse_args(argv)


def print_configuration(arguments: argparse.Namespace) -> None:
    print()
    print("==================================================")
    print("Simulated Clusterization")
    print("==================================================")
    print(f"Input          = {arguments.input_file}")
    print(f"Output dir     = {arguments.output_dir}")
    print(f"Output prefix  = {arguments.output_prefix}")
    print(f"Scratch dir    = {arguments.scratch_dir or '(system temporary folder)'}")
    setup = arguments.digitization
    provenance = setup.provenance

    if provenance["digitization_method"] == "npe_per_cm":
        print("Method         = path length x NPE/cm(Landau)")
        print(f"PE per cm file = {provenance['pe_per_cm_file']}")
        print(f"Detector       = {provenance['detector']}")
        print(f"Run range      = {provenance['run_range']}")

        for station, factor in sorted(setup.factors.items()):
            print(f"  station {station:>3}  = {factor:.3f} PE/cm")
    else:
        print("Method         = energy x Poisson")
        print(f"PE per MeV     = {setup.factors}")
        print(f"Detector       = {provenance['detector']}")

    print(f"RNG seed       = {arguments.rng_seed}")
    print(f"Seeding        = {SEEDING_SCHEME}")
    print(f"Chunk size     = {arguments.chunk_size:,}")
    print("==================================================")
    print()

def make_digitizer(setup, rng_seed):
    if setup.provenance["digitization_method"] == "npe_per_cm":
        return LandauPathDigitizer(pe_per_cm=setup.factors, rng_seed=rng_seed)
    else:
        return PoissonDigitizer(pe_per_mev=setup.factors, rng_seed=rng_seed)


def existing_chunks(folder: Path, prefix: str) -> list[Path]:
    """The {prefix}_part*.root files in folder, sorted."""
    if not folder.is_dir():
        return []

    start = f"{prefix}_part"

    return sorted(
        path
        for path in folder.iterdir()
        if path.name.startswith(start)
        and path.name.endswith(".root")
        and path.is_file()
    )


def publish_chunks(chunks: list[Path], destination: Path, prefix: str) -> list[Path]:
    """Copy this run's chunks to destination, then remove the other
    chunks of the prefix there, left from an earlier run (review point
    B2; there can be some only with --force). Returns those removed."""
    names = {chunk.name for chunk in chunks}

    for chunk in chunks:
        copy_into_place(chunk, destination / chunk.name)

    stale = [
        path
        for path in existing_chunks(destination, prefix)
        if path.name not in names
    ]

    for path in stale:
        path.unlink()

    return stale


def run_clusterization(arguments: argparse.Namespace) -> None:
    destination = arguments.output_dir
    prefix = arguments.output_prefix

    try:
        with scratch_folder(arguments.scratch_dir) as scratch:
            _run_in_scratch(arguments, scratch)
    except BaseException:
        # Nothing of the prefix is left, so a failed run cannot pass
        # for a complete one, nor mix with an earlier run's chunks.
        removed = existing_chunks(destination, prefix)

        for path in removed:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                print(f"WARNING: could not remove {path}: {error}")

        if removed:
            print(
                f"The run failed: removed {len(removed)} chunk(s) "
                f"{prefix}_part*.root from {destination}"
            )

        raise


def _run_in_scratch(arguments: argparse.Namespace, scratch: Path) -> None:
    reader = RootReader(str(arguments.input_file))

    writer = RootWriter(
        output_prefix=arguments.output_prefix,
        output_dir=scratch,
        chunk_size=arguments.chunk_size,
    )

    digitizer = make_digitizer(arguments.digitization, arguments.rng_seed)
    clusterizer = SimClusterizer(rng_seed=arguments.rng_seed)

    event_keys = reader.get_event_keys()

    events_with_clusters = 0
    events_without_clusters = 0
    total_clusters = 0

    for event_number, (process_id, event_id) in enumerate(event_keys):

        if (
            arguments.progress_every > 0
            and event_number % arguments.progress_every == 0
        ):
            print(
                f"Processing {event_number:,}/{len(event_keys):,}"
            )

        raw_hits = reader.read_event(process_id, event_id)

        if len(raw_hits) == 0:
            events_without_clusters += 1
            continue

        bar_hits = aggregate_bar_hits(raw_hits)
        digitized_hits = digitizer.digitize(bar_hits)
        planes = build_planes(digitized_hits)

        event_has_clusters = False

        for plane in planes:
            cluster_collection = clusterizer.cluster_plane(plane)

            records = cluster_collection_to_records(
                event=event_id,
                station=plane.station,
                cluster_collection=cluster_collection,
                plane=plane,
            )

            if len(records) > 0:
                event_has_clusters = True
                total_clusters += len(records)

            writer.extend(records)

        if event_has_clusters:
            events_with_clusters += 1
        else:
            events_without_clusters += 1

    writer.close()

    print()
    print("==================================================")
    print("Production Summary")
    print("==================================================")
    print(f"Unique event keys processed : {len(event_keys):,}")
    print(f"Events with clusters        : {events_with_clusters:,}")
    print(f"Events without clusters     : {events_without_clusters:,}")
    print(f"Total clusters              : {total_clusters:,}")

    if len(event_keys) > 0:
        efficiency = 100.0 * events_with_clusters / len(event_keys)
        clusters_per_event = total_clusters / len(event_keys)

        print(f"Cluster efficiency          : {efficiency:.2f}%")
        print(f"Clusters/event              : {clusters_per_event:.2f}")

    # Only this run's chunks, still in scratch: the run totals are known
    # only now, at the end.
    chunk_files = list(writer.written_files)

    if chunk_files:
        calibration = arguments.digitization.provenance.get("pe_per_cm_file")

        attach_provenance_to_many(
            chunk_files,
            stage="clusterization",
            detector=arguments.detector,
            extra_files=[calibration] if calibration else [],
            input_path=arguments.input_file,
            parameters={
                **arguments.digitization.provenance,
                "rng_seed": arguments.rng_seed,
                "seeding_scheme": SEEDING_SCHEME,
                "chunk_size": arguments.chunk_size,
                "output_prefix": arguments.output_prefix,
                "events_processed": len(event_keys),
                "total_clusters": total_clusters,
            },
            recorded_as=[
                arguments.output_dir / chunk.name for chunk in chunk_files
            ],
        )

    removed = publish_chunks(
        chunk_files,
        arguments.output_dir,
        arguments.output_prefix,
    )

    print(f"Copied {len(chunk_files)} chunk(s) to {arguments.output_dir}")

    if removed:
        print(
            f"Removed {len(removed)} chunk(s) left from an earlier run "
            f"(--force), e.g. {removed[0].name}"
        )

    print()
    print("Finished clusterization.")
    print()


def main(argv: list[str] | None = None) -> None:
    arguments = parse_arguments(argv)

    if arguments.rng_seed < 0:
        raise SystemExit("--rng-seed must be non-negative")

    # Resolved before the input is opened, so a configuration mistake
    # stops the run in seconds rather than after hours of processing.
    try:
        arguments.digitization = digitization_setup(
            pe_per_mev=arguments.pe_per_mev,
            pe_per_cm_file=arguments.pe_per_cm_file,
            detector=arguments.detector,
            run_range=arguments.run_range,
            default_pe_per_mev=DEFAULT_PE_PER_MEV,
        )
    except (ValueError, NotImplementedError) as error:
        raise SystemExit(f"error: {error}") from None

    for warning in arguments.digitization.warnings:
        print(f"WARNING: {warning}")

    input_file = arguments.input_file.expanduser().resolve()

    if not input_file.is_file():
        raise FileNotFoundError(input_file)

    arguments.input_file = input_file
    arguments.output_dir = arguments.output_dir.expanduser().resolve()

    try:
        arguments.scratch_dir = checked_scratch_dir(arguments.scratch_dir)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from None

    if arguments.output_prefix is None:
        arguments.output_prefix = (
            f"{input_file.stem}{arguments.digitization.tag}_clustered"
        )

    # Checked before any work: chunks of the same prefix from an earlier
    # run would otherwise be mixed with this run's (review point B2).
    existing = existing_chunks(arguments.output_dir, arguments.output_prefix)

    if existing and not arguments.force:
        raise SystemExit(
            f"error: {arguments.output_dir} already holds {len(existing)} "
            f"chunk(s) {arguments.output_prefix}_part*.root, e.g. "
            f"{existing[0].name}. Remove them, choose another -o or "
            "--output-prefix, or pass --force to replace them."
        )

    if existing:
        print(
            f"--force: the {len(existing)} chunk(s) {arguments.output_prefix}"
            "_part*.root already there will be replaced at the end of the run."
        )

    make_output_dir(arguments.output_dir)

    print_configuration(arguments)
    run_clusterization(arguments)


if __name__ == "__main__":
    main()
