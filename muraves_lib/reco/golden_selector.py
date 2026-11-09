"""Golden-track definition shared by the MURAVES data and simulation chains.

An event is *golden* when it has a valid best 3-plane XZ track AND a valid best
4-plane XZ track, i.e. neither best chi square is the "missing" sentinel written
by the tracking step. This is the same gate as the historical C++ macro
``AnalysisOfCluster_and_tracks4planes.C``.

The function works element-wise, so it accepts scalars (one event) as well as
numpy / awkward arrays (one entry per event) and returns a bool or a boolean mask.
"""
from __future__ import annotations

MISSING = -1


def is_golden(best_track_3p_chi_square_xz, best_track_4p_chi_square_xz):
    """Return True (or a boolean mask) where the event passes the golden gate."""
    return (best_track_3p_chi_square_xz != MISSING) & (best_track_4p_chi_square_xz != MISSING)
