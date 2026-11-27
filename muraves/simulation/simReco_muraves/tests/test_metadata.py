"""A2 and B4: the METADATA record and how it is stored and read.

uproot is replaced by a small in-memory stand-in, so these run without it;
tests/test_provenance.py checks the same with real ROOT files where uproot
is installed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from simReco_muraves import provenance as pv


class FakeFile:
    """What provenance_tree uses of an uproot file: in, [], and assignment."""

    def __init__(self, store: dict):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __contains__(self, key):
        return key in self.store

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value


class FakeBranch:
    def __init__(self, values):
        self.values = values

    def array(self, library="np"):
        return list(self.values)


class FakeUproot:
    """Files are dicts of stored objects, by path; a path that is not
    registered is not a ROOT file."""

    def __init__(self):
        self.files: dict[str, dict] = {}
        self.fail_update = False

    def add(self, path: Path, objects: dict | None = None) -> Path:
        path.write_text("stand-in for a ROOT file")
        self.files[str(path)] = dict(objects or {})
        return path

    def open(self, path):
        if str(path) not in self.files:
            raise ValueError(f"not a ROOT file: {path}")
        return FakeFile(self.files[str(path)])

    def update(self, path):
        if self.fail_update:
            raise OSError("Permission denied")
        return FakeFile(self.files[str(path)])


@pytest.fixture
def fake(monkeypatch):
    from simReco_muraves.io import provenance_tree

    stand_in = FakeUproot()
    monkeypatch.setattr(provenance_tree, "uproot", stand_in)
    monkeypatch.setattr(pv, "git_state", lambda: ("abc123", False))
    return provenance_tree, stand_in


def record(detector="NERO", stages=None):
    return {
        "commit": "abc123",
        "detector": detector,
        "stages": stages if stages is not None else [{"stage": "clusterization"}],
    }


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------

def test_write_and_read_back(fake, tmp_path):
    tree, uproot = fake
    path = uproot.add(tmp_path / "out.root")

    tree.write_metadata(path, record())

    stored = uproot.files[str(path)]["METADATA"]
    assert isinstance(stored, str)  # written as one string: a TObjString
    assert json.loads(stored) == record()
    assert tree.read_metadata(path) == record()
    assert tree.read_chain(path) == [{"stage": "clusterization"}]


def test_a_write_failure_is_an_error(fake, tmp_path):
    tree, uproot = fake
    path = uproot.add(tmp_path / "out.root")
    uproot.fail_update = True

    with pytest.raises(tree.ProvenanceError, match="could not write METADATA"):
        tree.write_metadata(path, record())


def test_a_record_that_does_not_read_back_is_an_error(fake, tmp_path, monkeypatch):
    tree, uproot = fake
    path = uproot.add(tmp_path / "out.root")
    monkeypatch.setattr(tree, "read_metadata", lambda path: record(detector="BLU"))

    with pytest.raises(tree.ProvenanceError, match="does not read back"):
        tree.write_metadata(path, record())


def test_a_file_without_a_record_reads_as_none(fake, tmp_path):
    tree, uproot = fake
    path = uproot.add(tmp_path / "hits.root", {"HitData": object()})

    assert tree.read_metadata(path) is None
    assert tree.read_chain(path) == []


@pytest.mark.parametrize(
    "stored, message",
    [
        ("{not json", "not valid JSON"),
        (json.dumps(["a list"]), "not a JSON object"),
        (json.dumps({"detector": "NERO"}), "no list of stages"),
        (json.dumps({"stages": []}), "records no detector"),
        (json.dumps({"stages": [], "detector": ""}), "records no detector"),
    ],
)
def test_an_unreadable_record_is_an_error(fake, tmp_path, stored, message):
    tree, uproot = fake
    path = uproot.add(tmp_path / "out.root", {"METADATA": stored})

    with pytest.raises(tree.ProvenanceError, match=message):
        tree.read_metadata(path)


def test_a_file_that_cannot_be_opened_is_an_error(fake, tmp_path):
    tree, _ = fake
    path = tmp_path / "broken.root"
    path.write_text("not ROOT")

    with pytest.raises(tree.ProvenanceError, match="cannot read the metadata of broken.root"):
        tree.read_metadata(path)


def test_a_missing_file_is_an_error(fake, tmp_path):
    tree, _ = fake

    with pytest.raises(FileNotFoundError):
        tree.read_metadata(tmp_path / "absent.root")


def test_the_legacy_tree_is_read(fake, tmp_path):
    tree, uproot = fake
    chain = [{"stage": "clusterization", "parameters": {"detector": "ROSSO"}}]
    path = uproot.add(
        tmp_path / "old.root",
        {"Metadata": {"provenance_json": FakeBranch([json.dumps(chain)])}},
    )

    assert tree.read_metadata(path) == {"stages": chain, "legacy": True}


def test_the_legacy_string_is_read(fake, tmp_path):
    tree, uproot = fake
    chain = [{"stage": "clusterization"}]
    path = uproot.add(tmp_path / "old.root", {"Metadata_json": json.dumps(chain)})

    assert tree.read_metadata(path) == {"stages": chain, "legacy": True}


def test_an_unreadable_legacy_record_is_an_error(fake, tmp_path):
    tree, uproot = fake
    path = uproot.add(tmp_path / "old.root", {"Metadata_json": "{broken"})

    with pytest.raises(tree.ProvenanceError, match="not valid JSON"):
        tree.read_metadata(path)


def test_new_record_wins_over_a_legacy_one(fake, tmp_path):
    tree, uproot = fake
    path = uproot.add(
        tmp_path / "out.root",
        {"METADATA": json.dumps(record()), "Metadata_json": json.dumps([{"stage": "old"}])},
    )

    assert tree.read_metadata(path) == record()


# ----------------------------------------------------------------------
# attach_provenance
# ----------------------------------------------------------------------

def test_attach_provenance_extends_the_inputs_lineage(fake, tmp_path):
    tree, uproot = fake
    upstream = uproot.add(
        tmp_path / "clustered.root", {"METADATA": json.dumps(record(stages=[{"stage": "clusterization"}]))}
    )
    downstream = uproot.add(tmp_path / "scratch_tracked.root")

    written = tree.attach_provenance(
        downstream, stage="tracking", detector="NERO", input_path=upstream,
        quiet=True, recorded_as="/pnfs/tracked.root",
    )

    assert tree.read_metadata(downstream) == written
    assert [entry["stage"] for entry in written["stages"]] == ["clusterization", "tracking"]
    assert written["stages"][-1]["input_file"] == str(upstream)
    assert written["stages"][-1]["output_file"] == "/pnfs/tracked.root"
    assert written["detector"] == "NERO"


def test_attach_provenance_fails_on_an_unreadable_input(fake, tmp_path):
    tree, uproot = fake
    upstream = uproot.add(tmp_path / "clustered.root", {"METADATA": "{broken"})
    downstream = uproot.add(tmp_path / "tracked.root")

    with pytest.raises(tree.ProvenanceError):
        tree.attach_provenance(downstream, stage="tracking", detector="NERO", input_path=upstream)

    assert "METADATA" not in uproot.files[str(downstream)]


def test_attach_provenance_to_many_records_the_calibration_without_its_content(fake, tmp_path):
    tree, uproot = fake
    hits = uproot.add(tmp_path / "hits.root", {"HitData": object()})
    chunks = [uproot.add(tmp_path / f"c_part{i:03d}.root") for i in range(2)]
    calibration = tmp_path / "npecm.json"
    calibration.write_text(json.dumps({"NERO": {"2500": {"Y1": 9.4}}}))

    tree.attach_provenance_to_many(
        chunks, stage="clusterization", detector="NERO", input_path=hits,
        parameters={"total_clusters": 6}, extra_files=[calibration],
    )

    for chunk in chunks:
        written = tree.read_metadata(chunk)
        entry = written["detector_config_files"][-1]
        assert entry["path"] == str(calibration.resolve())
        assert "sha256" in entry and "parsed_content" not in entry
        assert written["stages"][-1]["parameters"]["total_clusters"] == 6


# ----------------------------------------------------------------------
# The record
# ----------------------------------------------------------------------

def test_the_record_has_the_data_chains_keys_and_ours(monkeypatch):
    from muraves_lib.reco.reco_config import package_config_paths

    monkeypatch.setattr(pv, "git_state", lambda: ("abc123", False))
    metadata = pv.build_metadata(detector="ROSSO", stages=[{"stage": "tracking"}])

    assert {"commit", "latest_release", "algorithms", "generated_at"} <= set(metadata)
    assert metadata["detector"] == "ROSSO"
    assert metadata["stages"] == [{"stage": "tracking"}]
    assert metadata["simulation_metadata_version"] == pv.METADATA_VERSION

    files = metadata["detector_config_files"]
    assert [entry["path"] for entry in files] == [os.path.abspath(path) for path in package_config_paths("simulation")]
    assert all(len(entry["sha256"]) == 64 and "parsed_content" in entry for entry in files)
    json.dumps(metadata)  # storable as it is


@pytest.mark.parametrize("detector", [None, ""])
def test_the_record_needs_a_detector(detector):
    with pytest.raises(ValueError, match="needs the detector"):
        pv.build_metadata(detector=detector, stages=[], header={})


def test_the_commit_is_this_packages_checkout(tmp_path, monkeypatch):
    """get_git_metadata runs in the package's checkout, not in the folder the job runs from."""
    from muraves_lib import root_wrapper

    calls = []
    real = subprocess.check_output

    def spy(command, **options):
        calls.append(options.get("cwd"))
        return real(command, **options)

    monkeypatch.setattr(root_wrapper.subprocess, "check_output", spy)
    monkeypatch.chdir(tmp_path)

    pv.metadata_header()

    assert calls and all(Path(cwd) == pv.REPOSITORY_ROOT for cwd in calls)


def test_root_wrapper_imports_without_root():
    """The simulation uses root_wrapper's record helpers without ROOT."""
    code = (
        "import sys; sys.modules['ROOT'] = None\n"
        "from muraves_lib import root_wrapper\n"
        "assert 'commit' in root_wrapper.get_git_metadata()\n"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
