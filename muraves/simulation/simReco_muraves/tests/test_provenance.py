# simReco_muraves/tests/test_provenance.py

"""Provenance: building records, chaining them, storing them in ROOT.

The record logic is pure Python and tested directly. Storage as METADATA
in real ROOT files needs uproot and is skipped where it is not installed;
tests/test_metadata.py tests the same logic with uproot replaced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simReco_muraves import provenance as pv


# ----------------------------------------------------------------------
# Records
# ----------------------------------------------------------------------

@pytest.fixture
def clean_checkout(monkeypatch):
    monkeypatch.setattr(pv, "git_state", lambda: ("abc123", False))


def test_record_fields(clean_checkout):
    record = pv.build_stage_record(
        stage="tracking",
        input_file=Path("/data/in.root"),
        output_file="/data/out.root",
        parameters={"sigma_z": 0.004},
    )

    assert record["stage"] == "tracking"
    assert record["input_file"] == "/data/in.root"
    assert record["output_file"] == "/data/out.root"
    assert record["code_version"] == "abc123"
    assert record["code_dirty"] is False
    assert record["schema_version"] == pv.SCHEMA_VERSION
    assert set(record["libraries"]) == set(pv.TRACKED_LIBRARIES)
    assert record["timestamp"].endswith("Z")


def test_record_has_no_input_for_the_first_stage(clean_checkout):
    record = pv.build_stage_record(
        stage="clusterization",
        input_file=None,
        output_file="out.root",
    )

    assert record["input_file"] == ""
    assert record["parameters"] == {}


def test_parameters_are_made_json_safe(clean_checkout):
    record = pv.build_stage_record(
        stage="tracking",
        input_file=None,
        output_file="out.root",
        parameters={
            "x_pos": (-0.265, 0.0),
            "path": Path("/factors.json"),
            "nested": {"stations": (0, 8)},
            "flag": None,
        },
    )

    assert record["parameters"] == {
        "x_pos": [-0.265, 0.0],
        "path": "/factors.json",
        "nested": {"stations": [0, 8]},
        "flag": None,
    }
    json.dumps(record)


def test_schema_version_is_2():
    """Bump deliberately: update this test and the README table together."""
    assert pv.SCHEMA_VERSION == 2


# ----------------------------------------------------------------------
# Git state
# ----------------------------------------------------------------------

def test_outside_a_git_checkout_the_version_is_unknown(monkeypatch):
    monkeypatch.setattr(pv, "_run_git", lambda arguments: None)

    assert pv.git_state() == (pv.UNKNOWN, False)


def test_uncommitted_changes_are_detected(monkeypatch):
    responses = {"rev-parse": "abc123", "status": " M README.md"}
    monkeypatch.setattr(pv, "_run_git", lambda arguments: responses[arguments[0]])

    assert pv.git_state() == ("abc123", True)


def test_clean_tree_is_not_dirty(monkeypatch):
    responses = {"rev-parse": "abc123", "status": ""}
    monkeypatch.setattr(pv, "_run_git", lambda arguments: responses[arguments[0]])

    assert pv.git_state() == ("abc123", False)


# ----------------------------------------------------------------------
# Chaining
# ----------------------------------------------------------------------

def test_chain_appends_without_touching_the_upstream_record():
    upstream = [{"stage": "clusterization"}]

    chain = pv.extend_chain(upstream, {"stage": "tracking"})
    chain[0]["stage"] = "changed"

    assert [entry["stage"] for entry in chain] == ["changed", "tracking"]
    assert upstream == [{"stage": "clusterization"}]


def test_chain_can_start_from_nothing():
    assert pv.extend_chain(None, {"stage": "clusterization"}) == [
        {"stage": "clusterization"}
    ]


def test_chain_round_trips_through_json():
    chain = [{"stage": "a", "parameters": {"k": 1}}, {"stage": "b"}]

    assert pv.chain_from_json(pv.chain_to_json(chain)) == chain


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", []),
        ("not json", []),
        ('{"stage": "a"}', []),
        ('[{"stage": "a"}, 3, "b"]', [{"stage": "a"}]),
    ],
)
def test_unreadable_chains_degrade_to_what_can_be_kept(text, expected):
    assert pv.chain_from_json(text) == expected


# ----------------------------------------------------------------------
# Presentation
# ----------------------------------------------------------------------

def test_empty_chain_says_so():
    assert "No provenance recorded" in pv.summarize_chain([])


def test_summary_flags_a_dirty_tree():
    summary = pv.summarize_chain(
        [{"stage": "tracking", "code_version": "abc123", "code_dirty": True}]
    )

    assert "abc123 (uncommitted changes)" in summary


def test_summary_lists_parameters_in_order():
    summary = pv.summarize_chain(
        [{"stage": "clusterization", "parameters": {"rng_seed": 42, "pe_per_mev": 8.5}}]
    )

    assert summary.index("pe_per_mev = 8.5") < summary.index("rng_seed = 42")


# ----------------------------------------------------------------------
# Storage in ROOT files (real uproot)
# ----------------------------------------------------------------------

def provenance_tree():
    """The ROOT-storage module, or skip where uproot is not installed."""
    pytest.importorskip("uproot")
    from simReco_muraves.io import provenance_tree as module

    return module


def write_plain_file(path):
    import numpy
    import uproot

    with uproot.recreate(path) as root_file:
        root_file["Data"] = {"value": numpy.arange(3)}


def metadata(stages=None):
    return {
        "commit": "abc123",
        "latest_release": "v2.0.0",
        "algorithms": {},
        "generated_at": "2026-11-27T10:00:00",
        "detector_config_files": [],
        "detector": "NERO",
        "stages": stages if stages is not None else [{"stage": "clusterization"}],
        "simulation_metadata_version": 1,
    }


def test_metadata_round_trips_as_the_data_chains_tobjstring(tmp_path):
    tree = provenance_tree()
    import uproot

    path = tmp_path / "out.root"
    write_plain_file(path)
    tree.write_metadata(path, metadata())

    assert tree.read_metadata(path) == metadata()
    assert tree.read_chain(path) == [{"stage": "clusterization"}]

    with uproot.open(path) as root_file:
        # The data chain's format: a TObjString holding the JSON, under METADATA.
        assert root_file.classname_of("METADATA") == "TObjString"
        assert json.loads(str(root_file["METADATA"])) == metadata()


def test_writing_metadata_leaves_the_physics_tree_alone(tmp_path):
    tree = provenance_tree()
    import uproot

    path = tmp_path / "out.root"
    write_plain_file(path)
    tree.write_metadata(path, metadata())

    with uproot.open(path) as root_file:
        assert root_file["Data"]["value"].array(library="np").tolist() == [0, 1, 2]


def test_file_without_metadata_reads_as_none(tmp_path):
    tree = provenance_tree()

    path = tmp_path / "plain.root"
    write_plain_file(path)

    assert tree.read_metadata(path) is None
    assert tree.read_chain(path) == []


def test_missing_file_is_an_error(tmp_path):
    tree = provenance_tree()

    with pytest.raises(FileNotFoundError):
        tree.read_metadata(tmp_path / "absent.root")


def test_a_file_that_is_not_root_is_an_error(tmp_path):
    tree = provenance_tree()

    path = tmp_path / "broken.root"
    path.write_text("not a ROOT file")

    with pytest.raises(tree.ProvenanceError):
        tree.read_metadata(path)


def test_legacy_metadata_string_is_still_read(tmp_path):
    tree = provenance_tree()
    import uproot

    path = tmp_path / "old.root"
    write_plain_file(path)
    chain = [{"stage": "clusterization", "parameters": {"detector": "ROSSO"}}]

    with uproot.update(path) as root_file:
        root_file["Metadata_json"] = json.dumps(chain)

    assert tree.read_metadata(path) == {"stages": chain, "legacy": True}


def test_legacy_metadata_tree_is_still_read(tmp_path):
    tree = provenance_tree()
    import awkward
    import uproot

    path = tmp_path / "old.root"
    write_plain_file(path)
    chain = [{"stage": "clusterization", "parameters": {"detector": "ROSSO"}}]

    try:
        with uproot.update(path) as root_file:
            root_file["Metadata"] = {"provenance_json": awkward.Array([json.dumps(chain)])}
    except Exception as error:
        pytest.skip(f"this uproot cannot write string branches ({error}), so no legacy file has this form")

    assert tree.read_metadata(path) == {"stages": chain, "legacy": True}


def test_attach_provenance_chains_from_a_legacy_input(tmp_path, monkeypatch):
    tree = provenance_tree()
    import uproot

    monkeypatch.setattr(pv, "git_state", lambda: ("abc123", False))

    upstream = tmp_path / "clustered.root"
    downstream = tmp_path / "tracked.root"
    write_plain_file(upstream)
    write_plain_file(downstream)

    with uproot.update(upstream) as root_file:
        root_file["Metadata_json"] = json.dumps(
            [{"stage": "clusterization", "parameters": {"detector": "NERO"}}]
        )

    written = tree.attach_provenance(
        downstream,
        stage="tracking",
        detector="NERO",
        input_path=upstream,
        parameters={"sigma_z": 0.004},
        quiet=True,
    )

    assert tree.read_metadata(downstream) == written
    assert written["detector"] == "NERO"
    assert [entry["stage"] for entry in written["stages"]] == ["clusterization", "tracking"]
    assert {"commit", "latest_release", "algorithms", "generated_at", "detector_config_files"} <= set(written)


def test_the_data_chains_reader_reads_simulation_metadata(tmp_path):
    tree = provenance_tree()
    pytest.importorskip("ROOT")
    from muraves_lib import root_wrapper

    path = tmp_path / "out.root"
    write_plain_file(path)
    tree.write_metadata(path, metadata())

    assert root_wrapper.load_root_metadata(path) == metadata()
