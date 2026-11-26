"""Depth of 2-bar clusters inside a plane (method B of the residual-shape study).

The bars of a plane are triangles with alternating orientation (△ ▽ △ ▽ ...). A cluster of
two adjacent strips {k, k+1} means the muon crossed the face shared by the two bars, so
the cluster position measures where the track crosses that face. That is a 2D point:
position ``z_c`` at depth ``Xc`` with respect to the plane centre::

    k      = floor((z_c - first_strip_pos) / pitch)     # lower strip of the pair
    B      = first_strip_pos + (k + 1/2) * pitch        # shared face at the plane centre
    sign_k = +1 if k is even else -1
    Xc     = -face_orientation * sign_k * (h/p) * (z_c - B)

``|Xc| <= h/2`` by construction. Clusters of any other size get ``Xc = 0``, i.e. they stay
at the plane centre as before. The track fit then uses the point
``(x_pos + Xc, z_c + z_add)``.

``face_orientation`` is +1 when an (even, odd) strip pair shares a "\\" face (dz/dx < 0),
as in the simulated geometry, and -1 when the plane is mirrored. It is set per hodoscope
and view in the ``depth_correction`` section of the chain configuration files.

Study and decisions: ``dev/z_residual_shape/METHOD_B_IMPLEMENTATION_PLAN.md``.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

# Bar height / strip pitch. The triangle faces have |dz/dx| = 0.97 = pitch / height
# (Geant4 geometry check, dev/z_residual_shape/truth_bar_geometry_check.py).
# TODO: make it a parameter of the depth_correction configuration once the value preferred
# by the data (about 0.7, MC about 0.85) has been discussed.
NOMINAL_H_OVER_P = 1.0 / 0.97

VIEWS = ("z", "y")


def cluster_depths(
    positions: Sequence[float],
    sizes: Sequence[int],
    first_strip_pos: float,
    pitch: float,
    face_orientation: int | None,
    h_over_p: float = NOMINAL_H_OVER_P,
) -> list[float]:
    """Depth Xc [m] of each cluster of one plane: non-zero only for 2-strip clusters.

    ``positions`` are the cluster positions in the cluster frame (``ClustersPositions``,
    without ``z_add``/``y_add``) and ``sizes`` the matching ``ClustersSize``.
    ``face_orientation=None`` (orientation not known) returns all zeros.
    """
    if len(positions) != len(sizes):
        raise ValueError(f"{len(positions)} cluster positions but {len(sizes)} cluster sizes")
    if face_orientation is None:
        return [0.0] * len(positions)
    if face_orientation not in (1, -1):
        raise ValueError(f"face_orientation must be +1, -1 or None, got {face_orientation!r}")

    depths: list[float] = []
    for position, size in zip(positions, sizes):
        if size != 2:
            depths.append(0.0)
            continue
        k = math.floor((position - first_strip_pos) / pitch)
        boundary = first_strip_pos + (k + 0.5) * pitch
        sign_k = 1.0 if k % 2 == 0 else -1.0
        depths.append(-face_orientation * sign_k * h_over_p * (position - boundary))
    return depths


def face_orientation_for(config: dict[str, Any], hodoscope: str, view: str) -> int | None:
    """Face orientation to use for ``hodoscope`` and ``view`` ("z" or "y"), or None for no depths.

    None when the configuration has no ``depth_correction`` section (shared parameters
    only), when the correction is disabled, or when the orientation is ``null`` (not
    measured). An enabled correction with a hodoscope that is not listed is an error.
    """
    if view not in VIEWS:
        raise ValueError(f"view must be one of {VIEWS}, got {view!r}")
    section = config.get("depth_correction")
    if not section or not section.get("enabled", False):
        return None
    orientations = section.get("face_orientation", {})
    if hodoscope not in orientations:
        raise ValueError(
            f"depth_correction is enabled but face_orientation has no entry for {hodoscope!r} "
            f"(known: {sorted(k for k in orientations if not k.startswith('_'))})"
        )
    value = orientations[hodoscope].get(view)
    if value is None:
        return None
    if value not in (1, -1):
        raise ValueError(f"face_orientation.{hodoscope}.{view} must be +1, -1 or null, got {value!r}")
    return int(value)
