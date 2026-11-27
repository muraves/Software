"""The simulation's stand-in for the board time expansion.

In the data, each board records a time expansion, and the tracking uses
it as a validity flag (MakeTracks only selects a best 3-plane track
whose clusters all have one; the plane-4 selection takes the first
candidate that has one). The simulation has no electronics, hence no
time expansion: every cluster gets this constant, i.e. timing is always
valid. It is the value SimClusterizer gives CreateClusterList, and the
value the tracking receives.

The Geant4 time of a cluster (its earliest hit) is a physical time, not
a flag. It is kept as its own output (ClusterTime) and never used as a
time expansion (review point B3 of PR #26).
"""

from __future__ import annotations

from collections.abc import Sized

SIM_TIME_EXPANSION = 1.0


def time_expansions(clusters: Sized) -> list[float]:
    """One time expansion per cluster of a plane."""
    return [SIM_TIME_EXPANSION] * len(clusters)
