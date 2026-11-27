"""The simulated detector: its reconstruction geometry and calibration.

The detector is chosen once, at clustering (--detector), and recorded in
the METADATA of every output, as a required field written with the data
(review point B4 of PR #26). Tracking and golden selection read it from
their input, so a production cannot be reconstructed with another
detector's geometry by mistake. An input that records none, or whose
record cannot be read, is an error; --detector given again is only a
check, and must agree.

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
    """The detector a file records, or None if it records none.

    METADATA's detector field; in files written before METADATA, the
    clustering stage's detector parameter. A record that cannot be read
    raises (simReco_muraves.io.provenance_tree.ProvenanceError).
    """
    # Imported here: reading ROOT files needs uproot, the rest of this
    # module does not.
    from simReco_muraves.io.provenance_tree import read_metadata

    metadata = read_metadata(path)

    if metadata is None:
        return None

    if metadata.get("detector"):
        return metadata["detector"]

    detector = None
    for stage in metadata.get("stages", []):
        if stage.get("stage") == "clusterization":
            detector = (stage.get("parameters") or {}).get("detector")
    return detector


def detector_for(input_files: Iterable[str | Path], given: str | None) -> str:
    """The detector to reconstruct `input_files` with: the one they record.

    Every input must record one (review point B4); --detector (`given`)
    is only a check, and must agree.
    """
    recorded = {Path(path): recorded_detector(path) for path in input_files}

    if not recorded:
        raise ValueError("no input file to take the detector from")

    missing = [path.name for path, detector in recorded.items() if detector is None]

    if missing:
        raise ValueError(
            f"{missing[0]} records no detector: it was clustered before the "
            "detector was recorded. Cluster it again from its Geant4 hits "
            "(muraves-simCluster --detector ...), or reconstruct it with the "
            "standalone simReco-muraves repository (tag standalone-final)."
        )

    detectors = set(recorded.values())

    if len(detectors) > 1:
        raise ValueError(
            f"the inputs come from different detectors: {', '.join(sorted(detectors))}"
        )

    detector = detectors.pop()

    if given is not None and given != detector:
        raise ValueError(
            f"--detector {given} disagrees with the input, which was "
            f"clustered for {detector}"
        )

    tracking_geometry(detector)  # validates the name
    return detector
