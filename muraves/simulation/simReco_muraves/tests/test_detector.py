"""The simulated detector: geometry, calibration, and how a stage finds it."""

from __future__ import annotations

import json

import pytest

from muraves_lib.reco.reco_config import CONFIGURATION_DIR
from simReco_muraves import detector as dt
from simReco_muraves.clustering.conversion_factors import FALLBACK_SETTING


def shared_parameters() -> dict:
    return json.loads((CONFIGURATION_DIR / "shared" / "reco_parameters.json").read_text())


# ----------------------------------------------------------------------
# Geometry and calibration from the shared configuration
# ----------------------------------------------------------------------

def test_known_detectors_are_the_calibrated_ones():
    assert set(dt.known_detectors()) == set(FALLBACK_SETTING)


@pytest.mark.parametrize("name", ["NERO", "ROSSO", "BLU"])
def test_geometry_is_the_detector_entry_of_the_shared_configuration(name):
    shared = shared_parameters()
    geometry = dt.tracking_geometry(name)

    assert geometry.detector == name
    assert geometry.x_pos == shared["detector_geometry"][name]["x_pos"]
    assert geometry.z_add == shared["detector_geometry"][name]["z_add"]
    assert geometry.y_add == shared["reconstruction"]["y_add"]


def test_geometry_is_recorded_in_provenance_with_the_detector():
    parameters = dt.tracking_geometry("ROSSO").as_parameters()

    assert parameters["detector"] == "ROSSO"
    assert set(parameters) == {"detector", "x_pos", "z_add", "y_add"}


@pytest.mark.parametrize("name", ["GIALLO", "_note", ""])
def test_unknown_detector_has_no_geometry(name):
    with pytest.raises(ValueError, match="unknown detector"):
        dt.tracking_geometry(name)


def test_packaged_calibration_is_shipped_in_the_simulation_configuration():
    path = dt.packaged_calibration_file()

    assert path.parent == CONFIGURATION_DIR / "simulation"
    assert path.is_file()
    assert set(json.loads(path.read_text())) >= set(dt.known_detectors())


# ----------------------------------------------------------------------
# Which detector a stage reconstructs with
# ----------------------------------------------------------------------

@pytest.fixture
def recorded(monkeypatch):
    """Pretend each input file recorded the detector in this mapping."""
    files: dict[str, str | None] = {}
    monkeypatch.setattr(dt, "recorded_detector", lambda path: files[str(path)])
    return files


def test_detector_comes_from_the_input(recorded):
    recorded["a.root"] = "BLU"
    assert dt.detector_for(["a.root"], None) == "BLU"


def test_given_detector_may_repeat_the_recorded_one(recorded):
    recorded["a.root"] = "BLU"
    assert dt.detector_for(["a.root"], "BLU") == "BLU"


def test_given_detector_must_agree_with_the_input(recorded):
    recorded["a.root"] = "NERO"
    with pytest.raises(ValueError, match="disagrees"):
        dt.detector_for(["a.root"], "ROSSO")


def test_an_input_without_a_detector_is_refused_even_with_one_given(recorded):
    """B4: --detector is a check, never a substitute for the record."""
    recorded["old.root"] = None
    with pytest.raises(ValueError, match="old.root records no detector"):
        dt.detector_for(["old.root"], "ROSSO")


def test_no_detector_anywhere_is_an_error(recorded):
    recorded["old.root"] = None
    with pytest.raises(ValueError, match="Cluster it again"):
        dt.detector_for(["old.root"], None)


def test_one_input_without_a_detector_is_enough_to_refuse(recorded):
    recorded.update({"a.root": "NERO", "old.root": None})
    with pytest.raises(ValueError, match="old.root records no detector"):
        dt.detector_for(["a.root", "old.root"], None)


def test_inputs_from_different_detectors_are_an_error(recorded):
    recorded.update({"a.root": "NERO", "b.root": "BLU"})
    with pytest.raises(ValueError, match="different detectors"):
        dt.detector_for(["a.root", "b.root"], None)


def test_an_unknown_recorded_detector_is_an_error(recorded):
    recorded["a.root"] = "GIALLO"
    with pytest.raises(ValueError, match="unknown detector"):
        dt.detector_for(["a.root"], None)


def test_an_unreadable_record_is_an_error_not_a_missing_detector(monkeypatch):
    """B4: a read failure is never taken for "no detector recorded"."""
    pytest.importorskip("uproot")
    from simReco_muraves.io import provenance_tree

    def unreadable(path):
        raise provenance_tree.ProvenanceError("cannot read the metadata of a.root")

    monkeypatch.setattr(provenance_tree, "read_metadata", unreadable)

    with pytest.raises(provenance_tree.ProvenanceError):
        dt.detector_for(["a.root"], "NERO")


@pytest.fixture
def metadata_of(monkeypatch):
    """Pretend read_metadata returns this record."""
    pytest.importorskip("uproot")
    from simReco_muraves.io import provenance_tree

    record = {}
    monkeypatch.setattr(provenance_tree, "read_metadata", lambda path: record.get("value"))
    return record


def test_recorded_detector_is_the_metadata_field(metadata_of):
    metadata_of["value"] = {
        "detector": "BLU",
        "stages": [{"stage": "clusterization", "parameters": {}}],
    }

    assert dt.recorded_detector("any.root") == "BLU"


def test_recorded_detector_of_a_legacy_file_is_the_clustering_stage_one(metadata_of):
    metadata_of["value"] = {
        "legacy": True,
        "stages": [
            {"stage": "clusterization", "parameters": {"detector": "ROSSO"}},
            {"stage": "tracking", "parameters": {"detector": "ROSSO"}},
        ],
    }

    assert dt.recorded_detector("any.root") == "ROSSO"


def test_a_file_without_metadata_records_no_detector(metadata_of):
    metadata_of["value"] = None

    assert dt.recorded_detector("hits.root") is None
