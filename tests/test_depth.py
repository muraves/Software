"""Tests of muraves_lib.reco.depth (method B: depth of 2-bar clusters).

Run inside the muraves container:
    python -m pytest tests/
"""

from __future__ import annotations

import math
import random

import pytest

from muraves_lib.reco.depth import NOMINAL_H_OVER_P, cluster_depths, face_orientation_for
from muraves_lib.reco.reco_config import get_reco_config

C0 = -0.528
PITCH = 0.0165
N_STRIPS = 64
H = NOMINAL_H_OVER_P * PITCH  # bar height


def reference_depth(position: float, size: int, h_over_p: float, orientation: int) -> float:
    """Copy of depth() in dev/z_residual_shape/truth_size2_2dpoint_vs_posttrack.py (scalar form)."""
    k = math.floor((position - C0) / PITCH)
    boundary = C0 + (k + 0.5) * PITCH
    sign = 1.0 if k % 2 == 0 else -1.0
    return -orientation * sign * h_over_p * (position - boundary) if size == 2 else 0.0


def pair_positions(n: int, seed: int = 1) -> list[float]:
    """Random 2-strip cluster positions: between the centres of strips k and k+1."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        k = rng.randrange(N_STRIPS - 1)
        out.append(C0 + (k + rng.uniform(0.001, 0.999)) * PITCH)
    return out


def test_only_two_strip_clusters_get_a_depth():
    positions = [C0 + 3.4 * PITCH] * 5
    depths = cluster_depths(positions, [1, 2, 3, 4, 0], C0, PITCH, 1)
    assert depths[0] == 0.0 and depths[2:] == [0.0, 0.0, 0.0]
    assert depths[1] != 0.0


def test_no_orientation_means_no_depth():
    positions = pair_positions(50)
    assert cluster_depths(positions, [2] * 50, C0, PITCH, None) == [0.0] * 50


def test_empty_plane():
    assert cluster_depths([], [], C0, PITCH, 1) == []


def test_depth_stays_inside_the_plane():
    positions = pair_positions(5000)
    for orientation in (1, -1):
        depths = cluster_depths(positions, [2] * len(positions), C0, PITCH, orientation)
        assert max(abs(d) for d in depths) <= H / 2 + 1e-12


def test_point_on_the_boundary_is_at_the_plane_centre():
    for k in (0, 1, 30, 31, 62):
        boundary = C0 + (k + 0.5) * PITCH
        assert cluster_depths([boundary], [2], C0, PITCH, 1) == pytest.approx([0.0], abs=1e-15)


def test_sign_flips_with_parity_and_orientation():
    offset = 0.3 * PITCH  # same offset above the pair boundary, for an even and an odd lower strip
    even = C0 + (10 + 0.5) * PITCH + offset
    odd = C0 + (11 + 0.5) * PITCH + offset
    d_plus = cluster_depths([even, odd], [2, 2], C0, PITCH, 1)
    d_minus = cluster_depths([even, odd], [2, 2], C0, PITCH, -1)
    assert d_plus[0] == pytest.approx(-d_plus[1])
    assert d_minus == pytest.approx([-d for d in d_plus])
    # even lower strip, "\" face: a point above the boundary is crossed at negative depth
    assert d_plus[0] == pytest.approx(-NOMINAL_H_OVER_P * offset)


def test_point_on_the_face_is_mapped_to_its_depth():
    """A point placed on the shared face (simulated geometry, orientation +1) comes back at its true depth."""
    for k in (4, 5):  # even lower strip: "\" face z = B - (p/h) x ; odd: "/" face z = B + (p/h) x
        boundary = C0 + (k + 0.5) * PITCH
        face_slope = (-1.0 if k % 2 == 0 else 1.0) / NOMINAL_H_OVER_P
        for x_true in (-0.4 * H, -0.1 * H, 0.2 * H, 0.45 * H):
            z_face = boundary + face_slope * x_true
            assert cluster_depths([z_face], [2], C0, PITCH, 1) == pytest.approx([x_true], abs=1e-12)


def test_matches_the_study_implementation():
    positions = pair_positions(2000, seed=7)
    sizes = [random.Random(i).choice([1, 2, 2, 3]) for i in range(len(positions))]
    for orientation in (1, -1):
        for h_over_p in (NOMINAL_H_OVER_P, 0.7):
            got = cluster_depths(positions, sizes, C0, PITCH, orientation, h_over_p)
            want = [reference_depth(p, s, h_over_p, orientation) for p, s in zip(positions, sizes)]
            assert got == pytest.approx(want, abs=1e-15)


def test_bad_inputs():
    with pytest.raises(ValueError):
        cluster_depths([0.0], [2], C0, PITCH, 0)
    with pytest.raises(ValueError):
        cluster_depths([0.0, 0.1], [2], C0, PITCH, 1)


# --- configuration -------------------------------------------------------------------------

def _config(enabled, orientations):
    return {"depth_correction": {"enabled": enabled, "face_orientation": orientations}}


def test_orientation_from_config():
    cfg = _config(True, {"NERO": {"z": 1, "y": -1}, "BLU": {"z": None, "y": None}})
    assert face_orientation_for(cfg, "NERO", "z") == 1
    assert face_orientation_for(cfg, "NERO", "y") == -1
    assert face_orientation_for(cfg, "BLU", "z") is None
    with pytest.raises(ValueError):
        face_orientation_for(cfg, "VERDE", "z")
    with pytest.raises(ValueError):
        face_orientation_for(cfg, "NERO", "x")


def test_disabled_or_missing_section_means_no_depth():
    assert face_orientation_for(_config(False, {"NERO": {"z": 1, "y": -1}}), "NERO", "z") is None
    assert face_orientation_for({}, "NERO", "z") is None


def test_bad_orientation_value_in_config():
    with pytest.raises(ValueError):
        face_orientation_for(_config(True, {"NERO": {"z": 2, "y": -1}}), "NERO", "z")


@pytest.mark.parametrize("chain", ["data", "simulation"])
def test_package_configuration(chain):
    cfg = get_reco_config(chain=chain)
    assert cfg["depth_correction"]["enabled"] is False
    for hodoscope in ("NERO", "BLU", "ROSSO"):
        for view in ("z", "y"):
            assert face_orientation_for(cfg, hodoscope, view) is None  # disabled by default
    strips = cfg["strips"]
    assert strips["first_strip_pos"] == C0 and strips["adjacent_strips_distance"] == PITCH
