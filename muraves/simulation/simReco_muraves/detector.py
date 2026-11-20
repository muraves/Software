"""The simulated detector: its reconstruction geometry and calibration.

The detector is chosen once, at clustering (--detector), and recorded in
the provenance of every output. Tracking and golden selection read it
from their input, so a production cannot be reconstructed with another
detector's geometry by mistake; given again, it must agree.

The geometry is the detector's entry in the shared reconstruction
configuration (detector_geometry), the same one the data chain uses: the
simulated productions are generated with exactly that geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from muraves_lib.reco.reco_config import CONFIGURATION_DIR, get_reco_config


def _configuration() -> dict:
    return get_reco_config(chain="simulation")


def known_detectors() -> tuple[str, ...]:
    """Detectors with a geometry in the shared configuration."""
    return tuple(
        name for name in _configuration()["detector_geometry"]
        if not name.startswith("_")
    )


@dataclass(frozen=True)
class TrackingGeometry:
    detector: str
    x_pos: list[float]
    z_add: list[float]
    y_add: list[float]

    def as_parameters(self) -> dict:
        """The values recorded in provenance."""
        return {
            "detector": self.detector,
            "x_pos": self.x_pos,
            "z_add": self.z_add,
            "y_add": self.y_add,
        }


def tracking_geometry(detector: str) -> TrackingGeometry:
    """Plane positions and offsets of `detector`, from the configuration."""
    configuration = _configuration()
    geometry = configuration["detector_geometry"].get(detector)

    if geometry is None or detector.startswith("_"):
        raise ValueError(
            f"unknown detector {detector!r}; expected one of "
            f"{', '.join(known_detectors())}"
        )

    return TrackingGeometry(
        detector=detector,
        x_pos=[float(value) for value in geometry["x_pos"]],
        z_add=[float(value) for value in geometry["z_add"]],
        y_add=[float(value) for value in configuration["reconstruction"]["y_add"]],
    )


def packaged_calibration_file() -> Path:
    """The NPE/cm calibration shipped with the package (simulation configuration)."""
    name = _configuration()["digitization"]["pe_per_cm_file"]
    return CONFIGURATION_DIR / "simulation" / name


def recorded_detector(path: str | Path) -> str | None:
    """The detector the clustering stage recorded in a file's provenance."""
    # Imported here: reading ROOT files needs uproot, the rest of this
    # module does not.
    from simReco_muraves.io.provenance_tree import read_chain

    detector = None
    for stage in read_chain(path):
        if stage.get("stage") == "clusterization":
            detector = (stage.get("parameters") or {}).get("detector")
    return detector


def detector_for(input_files: Iterable[str | Path], given: str | None) -> str:
    """The detector to reconstruct `input_files` with.

    Taken from the inputs' provenance; --detector (`given`) is needed only
    for inputs that record none, and must agree with what they record.
    """
    recorded = {recorded_detector(path) for path in input_files} - {None}

    if len(recorded) > 1:
        raise ValueError(
            f"the inputs come from different detectors: {', '.join(sorted(recorded))}"
        )

    from_inputs = next(iter(recorded), None)

    if given is not None and from_inputs is not None and given != from_inputs:
        raise ValueError(
            f"--detector {given} disagrees with the input, which was "
            f"clustered for {from_inputs}"
        )

    detector = given or from_inputs

    if detector is None:
        raise ValueError(
            "the input records no detector (clustered before --detector "
            "existed); give --detector"
        )

    tracking_geometry(detector)  # validates the name
    return detector
