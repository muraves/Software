# simReco_muraves/cli/common.py

"""What the three command-line tools share: the output checks, the
--scratch-dir option, and recognising a ROOT file by the tree it holds.

Outputs are written through scratch (muraves_lib.file_handler
scratch_to_output and copy_into_place): the tools never write at the
destination directly, so they work on /pnfs, and a failed run leaves
nothing under its output names (review point A1 of PR #26).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable, Iterable

from muraves_lib.file_handler import make_output_dir


# The tree each stage writes, in the order a file is classified.
TREE_TYPES = (
    ("TrackedData", "tracked"),
    ("ClusteredData", "clustered"),
    ("Tracks4ptree", "golden"),
)


def add_scratch_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scratch-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Existing folder for the scratch copy of the output, which is "
            "written there first and then copied to its destination "
            "(default: the system's temporary folder, which follows $TMPDIR)."
        ),
    )


def checked_scratch_dir(scratch_dir: Path | None) -> Path | None:
    """The --scratch-dir value, resolved; it must be an existing folder."""
    if scratch_dir is None:
        return None

    scratch_dir = scratch_dir.expanduser().resolve()

    if not scratch_dir.is_dir():
        raise ValueError(f"--scratch-dir is not an existing folder: {scratch_dir}")

    return scratch_dir


def prepare_output(
    input_file: Path,
    output_file: Path | None,
    *,
    force: bool,
    default_name: Callable[[Path], Path],
) -> Path:
    """The output path, checked before any work is done.

    Defaults to default_name(input_file). Refuses an existing output
    unless force, and an output that is the input itself. Creates the
    output folder if needed (group-writable).
    """
    if output_file is None:
        output_file = default_name(input_file)

    # Resolved so that the overwrite check, the printed path and the
    # recorded provenance all refer to the same location.
    output_file = output_file.expanduser().resolve()

    if output_file == input_file.expanduser().resolve():
        raise ValueError(f"the output would replace the input: {output_file}")

    if output_file.is_dir():
        raise IsADirectoryError(f"Output path is a directory: {output_file}")

    if output_file.exists() and not force:
        raise FileExistsError(
            f"Output already exists: {output_file} "
            "(pass --force to overwrite)"
        )

    make_output_dir(output_file.parent)

    return output_file


def root_file_type(path: Path) -> str:
    """tracked, clustered, golden or unknown, from the tree the file holds."""
    import uproot

    with uproot.open(path) as root_file:
        for tree_name, file_type in TREE_TYPES:
            if tree_name in root_file:
                return file_type

    return "unknown"


def select_by_type(
    folder: Path,
    wanted: Iterable[str],
    *,
    file_type: Callable[[Path], str] | None = None,
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """The folder's *.root files, by the tree they hold, not by name
    (review point B6): (selected, skipped), each a sorted list of
    (path, type). A file that cannot be opened is an error."""
    file_type = file_type or root_file_type
    wanted = set(wanted)
    selected: list[tuple[Path, str]] = []
    skipped: list[tuple[Path, str]] = []

    for path in sorted(folder.glob("*.root")):
        if not path.is_file():
            continue

        try:
            kind = file_type(path)
        except Exception as error:
            raise ValueError(
                f"cannot read {path.name} to tell its type: "
                f"{type(error).__name__}: {error}"
            ) from error

        (selected if kind in wanted else skipped).append((path, kind))

    return selected, skipped


def print_skipped(skipped: list[tuple[Path, str]]) -> None:
    """One line per type; files of unknown type are named."""
    counts: dict[str, int] = {}

    for _, kind in skipped:
        counts[kind] = counts.get(kind, 0) + 1

    for kind, count in sorted(counts.items()):
        print(f"Skipping {count:,} {kind} file(s)")

    for path, kind in skipped:
        if kind == "unknown":
            print(f"  unknown: {path.name}")
