"""Tests of MakeTracks with per-cluster depths (method B).

A straight muon track is generated and, on each plane, a 2-strip cluster is placed where the
track crosses the face shared by the two bars (simulated geometry, face_orientation = +1).
With the depths from cluster_depths the fit must recover the track exactly; without them the
same clusters do not lie on a line.

Run inside the muraves container:
    python -m pytest muraves_lib/reco/tests
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict

import pytest

from muraves_lib.reco.depth import NOMINAL_H_OVER_P, cluster_depths
import muraves_lib.reco.tracking as tracking_module
from muraves_lib.reco.tracking import MakeTracks

C0 = -0.528
PITCH = 0.0165
H = NOMINAL_H_OVER_P * PITCH
X_POS = [-0.26, 0.0, 0.262, 1.492]  # NERO
Z_ADD = [0.293, 0.251, 0.21, 0.0]
SIGMA = 0.004
STRIPS = {"first_strip_pos": C0, "adjacent_strips_distance": PITCH, "n_strips": 64}
TRACKING = {"scattering_pi": 3.14159}


def face_crossing(plane: int, q: float, s: float) -> tuple[float, float]:
    """(cluster position z_c, depth x) where the line z = q + s*x crosses a shared face of the plane."""
    z_centre = q + s * X_POS[plane] - Z_ADD[plane]
    k0 = math.floor((z_centre - C0) / PITCH)
    for k in range(k0 - 3, k0 + 4):
        boundary = C0 + (k + 0.5) * PITCH
        face = (-1.0 if k % 2 == 0 else 1.0) / NOMINAL_H_OVER_P  # dz/dx of the k|k+1 face
        x = (q + s * X_POS[plane] - Z_ADD[plane] - boundary) / (face - s)
        z_c = boundary + face * x
        if abs(x) <= H / 2 and math.floor((z_c - C0) / PITCH) == k:
            return z_c, x
    raise AssertionError(f"no face crossing found on plane {plane}")


def run(clusters, sizes, with_depths: bool, proximity_cut: float = 5 * SIGMA):
    depths = [cluster_depths(c, s, C0, PITCH, 1) for c, s in zip(clusters, sizes)] if with_depths else [None] * 4
    zeros = [[0.0] * len(c) for c in clusters]
    return MakeTracks(
        *clusters,
        *[[10.0] * len(c) for c in clusters],  # energies
        *[[1.0] * len(c) for c in clusters],  # Texp
        proximity_cut, X_POS, Z_ADD, SIGMA,
        tracking_cfg=TRACKING, strips_cfg=STRIPS,
        depth_1=depths[0], depth_2=depths[1], depth_3=depths[2], depth_4=depths[3],
    ), zeros


def make_event(q: float, s: float, p2_size: int = 2):
    """One 2-strip cluster per plane on the track; P2 can instead be a 1-strip cluster at the plane centre."""
    clusters, sizes, true_x = [], [], []
    for plane in range(4):
        if plane == 1 and p2_size == 1:
            z_c, x = q + s * X_POS[1] - Z_ADD[1], 0.0
        else:
            z_c, x = face_crossing(plane, q, s)
        clusters.append([z_c])
        sizes.append([2 if not (plane == 1 and p2_size == 1) else 1])
        true_x.append(x)
    return clusters, sizes, true_x


TRACKS = [(0.0, 0.3), (0.3, -0.3), (0.1, 0.15)]


@pytest.mark.parametrize("q, s", TRACKS)
def test_depths_recover_the_track(q, s):
    clusters, sizes, true_x = make_event(q, s)
    depths = [cluster_depths(c, z, C0, PITCH, 1)[0] for c, z in zip(clusters, sizes)]
    assert depths == pytest.approx(true_x, abs=1e-12)

    tracks, _ = run(clusters, sizes, with_depths=True)
    assert len(tracks.slopes_3p) == 1
    assert tracks.slopes_3p[0] == pytest.approx(s, abs=1e-9)
    assert tracks.intercepts_3p[0] == pytest.approx(q, abs=1e-9)
    assert tracks.chiSquares_3p[0] == pytest.approx(0.0, abs=1e-12)
    for r in (tracks.residue_c1, tracks.residue_c2, tracks.residue_c3, tracks.Track_3p_ExpectedRes_p2):
        assert r[0] == pytest.approx(0.0, abs=1e-9)
    # plane 4: on the extrapolated track, so no displacement, no scattering, perfect 4p fit
    assert tracks.Plane4th_isIntercepted == [1]
    assert tracks.displacement_p4[0][0] == pytest.approx(0.0, abs=1e-9)
    assert tracks.chiSquares_4p[0][0] == pytest.approx(0.0, abs=1e-12)
    assert tracks.residue_c4_p4[0][0] == pytest.approx(0.0, abs=1e-9)
    assert tracks.ScatteringAngles[0][0] == pytest.approx(0.0, abs=1e-4)


@pytest.mark.parametrize("q, s", TRACKS)
def test_without_depths_the_clusters_are_off_the_line(q, s):
    clusters, sizes, _ = make_event(q, s)
    tracks, _ = run(clusters, sizes, with_depths=False)
    assert len(tracks.slopes_3p) == 1
    assert tracks.chiSquares_3p[0] > 1e-4


def test_mixed_cluster_sizes():
    """A 1-strip cluster keeps depth 0 and fits together with 2-strip clusters at their depths."""
    q, s = 0.0, 0.3
    clusters, sizes, _ = make_event(q, s, p2_size=1)
    assert sizes[1] == [1]
    tracks, _ = run(clusters, sizes, with_depths=True)
    assert tracks.slopes_3p[0] == pytest.approx(s, abs=1e-9)
    assert tracks.chiSquares_3p[0] == pytest.approx(0.0, abs=1e-12)


def test_candidate_cut_uses_the_depths():
    """With a tight proximity cut the track is found only when the P2 prediction uses the depths."""
    q, s = 0.0, 0.3
    clusters, sizes, _ = make_event(q, s)
    loose, _ = run(clusters, sizes, with_depths=False)
    off = abs(loose.Track_3p_ExpectedRes_p2[0])
    assert off > 1e-4
    cut = off / 2
    without, _ = run(clusters, sizes, with_depths=False, proximity_cut=cut)
    with_d, _ = run(clusters, sizes, with_depths=True, proximity_cut=cut)
    assert len(without.slopes_3p) == 0
    assert len(with_d.slopes_3p) == 1


def test_no_depths_equals_zero_depths():
    """depth_<plane>=None and explicit zeros give exactly the same output."""
    clusters = [[-0.2, 0.05, 0.31], [0.0, -0.12], [0.1, 0.2, -0.3], [0.05, 0.4]]
    energies = [[float(10 + i) for i in range(len(c))] for c in clusters]
    texp = [[1.0] * len(c) for c in clusters]
    common = dict(tracking_cfg=TRACKING, strips_cfg=STRIPS)
    args = (*clusters, *energies, *texp, 1.0, X_POS, Z_ADD, SIGMA)
    a = MakeTracks(*args, **common)
    b = MakeTracks(*args, **common, depth_1=[0.0] * 3, depth_2=[0.0] * 2, depth_3=[0.0] * 3, depth_4=[0.0] * 2)
    assert len(a.slopes_3p) > 0
    assert asdict(a) == asdict(b)


def test_depth_length_must_match():
    clusters = [[0.0], [0.0], [0.0], []]
    with pytest.raises(ValueError):
        MakeTracks(*clusters, *([[]] * 4), *([[]] * 4), 1.0, X_POS, Z_ADD, SIGMA,
                   tracking_cfg=TRACKING, strips_cfg=STRIPS, depth_2=[0.0, 0.0])


def test_warning_when_enabled_but_no_depths(monkeypatch, caplog):
    """Correction enabled in the configuration and MakeTracks called without depths:
    one warning per process; explicit depths (also zeros) do not warn."""
    clusters = [[0.0], [0.0], [0.0], []]
    args = (*clusters, *([[1.0]] * 3), [], *([[1.0]] * 3), [], 1.0, X_POS, Z_ADD, SIGMA)
    common = dict(tracking_cfg=TRACKING, strips_cfg=STRIPS)
    zeros = dict(depth_1=[0.0], depth_2=[0.0], depth_3=[0.0], depth_4=[])
    monkeypatch.setattr(tracking_module, "get_reco_config", lambda: {"depth_correction": {"enabled": True}})

    def warnings():
        return [r for r in caplog.records if r.levelno == logging.WARNING and "depth_correction" in r.getMessage()]

    with caplog.at_level(logging.WARNING, logger="muraves_lib.reco.tracking"):
        monkeypatch.setattr(tracking_module, "_warned_missing_depths", False)
        MakeTracks(*args, **common, **zeros)
        assert warnings() == []
        MakeTracks(*args, **common)
        MakeTracks(*args, **common)
        assert len(warnings()) == 1
        assert "issues/32" in warnings()[0].getMessage()

        caplog.clear()
        monkeypatch.setattr(tracking_module, "_warned_missing_depths", False)
        monkeypatch.setattr(tracking_module, "get_reco_config", lambda: {"depth_correction": {"enabled": False}})
        MakeTracks(*args, **common)
        assert warnings() == []
