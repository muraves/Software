"""B3: the simulation passes a constant time expansion, never the Geant4 time."""

from __future__ import annotations

from simReco_muraves.clustering import sim_clusterizer
from simReco_muraves.time_expansion import SIM_TIME_EXPANSION, time_expansions


def test_one_constant_time_expansion_per_cluster():
    assert SIM_TIME_EXPANSION == 1.0
    assert time_expansions([object()] * 3) == [1.0, 1.0, 1.0]
    assert time_expansions([]) == []


def test_the_clusterizer_passes_the_same_constant(monkeypatch):
    received = {}

    def fake_create_cluster_list(**kwargs):
        received.update(kwargs)
        return "clusters"

    monkeypatch.setattr(sim_clusterizer, "CreateClusterList", fake_create_cluster_list)
    plane = sim_clusterizer.Plane64(process_id=1, event=2, station=8)

    assert sim_clusterizer.SimClusterizer(rng_seed=1).cluster_plane(plane) == "clusters"
    assert received["Texp1"] == received["Texp2"] == SIM_TIME_EXPANSION
