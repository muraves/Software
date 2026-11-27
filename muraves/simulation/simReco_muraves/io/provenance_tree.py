# simReco_muraves/io/provenance_tree.py

"""Store the provenance inside the ROOT file it describes.

A sidecar file can be separated from its data; an in-file record
cannot. The record is the data chain's (review point A2 of PR #26): a
JSON string under the key METADATA, with the data chain's top-level
keys plus detector, the simulated detector (review point B4), and
stages, the lineage (simReco_muraves.provenance.build_metadata). The
data chain's tools (root_wrapper.load_root_metadata, print_metadata.py)
read it as they read their own files.

It is written into the scratch copy of an output, before the copy to the
destination (simReco_muraves.cli.common), so it works on /pnfs, where
files cannot be modified in place. Writing is strict: a failure raises
ProvenanceError, and the stage fails with no output.

Reading is strict too: a record that is present but cannot be read
raises ProvenanceError, so a check relying on it (the detector, B4) can
never pass by default. Files written before METADATA hold the lineage in
a one-entry tree named Metadata (or a string named Metadata_json); they
are still read. A file with no record at all (a Geant4 input) reads as
None.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import uproot

from ..provenance import (
    build_metadata,
    build_stage_record,
    extend_chain,
    metadata_header,
)


#: The data chain's key: a TObjString holding the JSON record.
METADATA_KEY = "METADATA"

#: Before METADATA (read only): a one-entry tree, or a string.
LEGACY_TREE_NAME = "Metadata"
LEGACY_OBJECT_NAME = "Metadata_json"
LEGACY_JSON_BRANCH = "provenance_json"


class ProvenanceError(ValueError):
    """A metadata record that cannot be written, or is present but unreadable."""


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------

def _text(stored: Any) -> str:
    """The string a stored TObjString (or string branch value) holds."""
    if isinstance(stored, bytes):
        return stored.decode("utf-8")

    if isinstance(stored, str):
        return str(stored)

    member = getattr(stored, "member", None)

    if member is not None:
        text = member("fString")
        return text.decode("utf-8") if isinstance(text, bytes) else str(text)

    raise ProvenanceError(f"unexpected stored object {type(stored).__name__}")


def _parse_metadata(text: str, name: str) -> dict[str, Any]:
    try:
        metadata = json.loads(text)
    except ValueError as error:
        raise ProvenanceError(f"{name}: METADATA is not valid JSON: {error}") from error

    if not isinstance(metadata, dict):
        raise ProvenanceError(f"{name}: METADATA is not a JSON object")

    stages = metadata.get("stages")

    if not isinstance(stages, list) or not all(isinstance(entry, dict) for entry in stages):
        raise ProvenanceError(f"{name}: METADATA has no list of stages")

    detector = metadata.get("detector")

    if not isinstance(detector, str) or not detector:
        raise ProvenanceError(f"{name}: METADATA records no detector")

    return metadata


def _parse_legacy_chain(text: str, name: str) -> list[dict[str, Any]]:
    try:
        chain = json.loads(text)
    except ValueError as error:
        raise ProvenanceError(f"{name}: the Metadata lineage is not valid JSON: {error}") from error

    if not isinstance(chain, list) or not all(isinstance(entry, dict) for entry in chain):
        raise ProvenanceError(f"{name}: the Metadata lineage is not a list of stages")

    return chain


def read_metadata(path: str | Path) -> dict[str, Any] | None:
    """The metadata a ROOT file holds, or None if it holds none.

    A METADATA record is returned as written. A record from before
    METADATA is returned as {"stages": lineage, "legacy": True}. A record
    that is present but unreadable, or a file that cannot be opened,
    raises.
    """
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    name = file_path.name

    try:
        with uproot.open(file_path) as root_file:
            if METADATA_KEY in root_file:
                return _parse_metadata(_text(root_file[METADATA_KEY]), name)

            if LEGACY_TREE_NAME in root_file:
                values = root_file[LEGACY_TREE_NAME][LEGACY_JSON_BRANCH].array(library="np")

                if len(values) != 1:
                    raise ProvenanceError(f"{name}: the Metadata tree has {len(values)} entries, not 1")

                return {"stages": _parse_legacy_chain(_text(values[0]), name), "legacy": True}

            if LEGACY_OBJECT_NAME in root_file:
                chain = _parse_legacy_chain(_text(root_file[LEGACY_OBJECT_NAME]), name)
                return {"stages": chain, "legacy": True}
    except ProvenanceError:
        raise
    except Exception as error:
        raise ProvenanceError(
            f"cannot read the metadata of {name}: {type(error).__name__}: {error}"
        ) from error

    return None


def read_chain(path: str | Path) -> list[dict[str, Any]]:
    """The lineage a ROOT file records: [] if it records none."""
    metadata = read_metadata(path)
    return list(metadata["stages"]) if metadata is not None else []


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------

def write_metadata(path: str | Path, metadata: Mapping[str, Any]) -> None:
    """Add METADATA to an existing ROOT file, and read it back.

    Use it on the scratch copy of an output (uproot.update rewrites the
    file). Raises ProvenanceError if it cannot be written or does not
    read back as written.
    """
    file_path = Path(path)
    text = json.dumps(dict(metadata), sort_keys=True)

    try:
        with uproot.update(file_path) as root_file:
            root_file[METADATA_KEY] = text
    except Exception as error:
        raise ProvenanceError(
            f"could not write METADATA into {file_path.name}: {type(error).__name__}: {error}"
        ) from error

    if read_metadata(file_path) != json.loads(text):
        raise ProvenanceError(f"METADATA in {file_path.name} does not read back as written")


def attach_provenance(
    output_path: str | Path,
    *,
    stage: str,
    detector: str,
    input_path: str | Path | None = None,
    parameters: Mapping[str, Any] | None = None,
    quiet: bool = False,
    recorded_as: str | Path | None = None,
    header: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write this stage's METADATA into an output file.

    The lineage is the input's (if any), plus a record of this stage.
    recorded_as is the output path the record names, when the file is
    written in scratch and copied to its destination afterwards (default:
    output_path). header is metadata_header(), when the caller has
    already built it. Returns the record; raises on any failure.
    """
    upstream = read_chain(input_path) if input_path is not None else []

    record = build_stage_record(
        stage=stage,
        input_file=input_path,
        output_file=recorded_as if recorded_as is not None else output_path,
        parameters=parameters,
    )

    chain = extend_chain(upstream, record)
    metadata = build_metadata(detector=detector, stages=chain, header=header)

    write_metadata(output_path, metadata)

    if not quiet:
        print(f"  metadata        : METADATA, {len(chain)} stage(s), detector {detector}")

    return metadata


def attach_provenance_to_many(
    output_paths: Sequence[str | Path],
    *,
    stage: str,
    detector: str,
    input_path: str | Path | None = None,
    parameters: Mapping[str, Any] | None = None,
    recorded_as: Sequence[str | Path] | None = None,
    extra_files: Sequence[str | Path] = (),
) -> int:
    """Attach the same stage record to several output files.

    Used by clusterization, whose output is split into chunks.
    recorded_as, if given, holds the path each record names, one per
    output file (see attach_provenance). extra_files are recorded with
    their SHA-256 (metadata_header). Returns the number of files
    annotated; raises on the first failure.
    """
    if recorded_as is None:
        recorded_as = list(output_paths)
    elif len(recorded_as) != len(output_paths):
        raise ValueError("recorded_as needs one path per output file")

    header = metadata_header(extra_files=extra_files)

    for output_path, recorded_path in zip(output_paths, recorded_as):
        attach_provenance(
            output_path,
            stage=stage,
            detector=detector,
            input_path=input_path,
            parameters=parameters,
            quiet=True,
            recorded_as=recorded_path,
            header=header,
        )

    print(f"  metadata        : METADATA in {len(output_paths)} file(s), detector {detector}")

    return len(output_paths)
