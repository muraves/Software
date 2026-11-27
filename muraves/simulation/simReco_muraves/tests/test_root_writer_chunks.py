"""B1: a ClusteredData chunk ends only between events."""

from __future__ import annotations

import pytest

from simReco_muraves.io import root_writer
from simReco_muraves.models.cluster_record import ClusterRecord


@pytest.fixture
def written(monkeypatch, tmp_path):
    """The (ProcessID, Event) of every cluster, chunk by chunk, without writing ROOT files."""
    chunks = []

    def build_tree_data(self):
        return {"ProcessID": list(self.process_id), "Event": list(self.event)}

    class FakeFile:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __setitem__(self, name, data):
            chunks.append(list(zip(data["ProcessID"], data["Event"])))

    monkeypatch.setattr(root_writer.RootWriter, "_build_tree_data", build_tree_data)
    monkeypatch.setattr(root_writer.uproot, "recreate", FakeFile)
    return chunks


def clusters_of(events):
    """`events` maps (ProcessID, Event) to its number of clusters, in order."""
    for (process_id, event), n in events:
        for cluster_id in range(n):
            yield ClusterRecord(
                process_id=process_id, event=event, station=8, cluster_id=cluster_id,
                cluster_multiplicity=n, cluster_energy=20.0, cluster_position=0.0,
                cluster_size=1, cluster_time=5.0, cluster_time_spread=0.0,
                strip_ids=[10], strip_energies=[20.0],
            )


EVENTS = [((0, 1), 3), ((0, 2), 4), ((0, 3), 2), ((1, 1), 5), ((1, 4), 1), ((2, 1), 6)]


@pytest.mark.parametrize("chunk_size", [1, 2, 5, 7, 100])
def test_no_event_is_split_across_chunks(written, tmp_path, chunk_size):
    writer = root_writer.RootWriter(output_dir=tmp_path, chunk_size=chunk_size)
    writer.extend(clusters_of(EVENTS))
    writer.close()

    events_per_chunk = [set(chunk) for chunk in written]
    seen = set()
    for events in events_per_chunk:
        assert not events & seen, "an event appears in two chunks"
        seen |= events

    assert [key for chunk in written for key in chunk] == [k for k, n in EVENTS for _ in range(n)]
    assert writer.n_written == sum(n for _, n in EVENTS)
    assert all(len(chunk) >= chunk_size for chunk in written[:-1])


def test_a_chunk_exceeds_the_size_by_at_most_one_event(written, tmp_path):
    writer = root_writer.RootWriter(output_dir=tmp_path, chunk_size=5)
    writer.extend(clusters_of(EVENTS))
    writer.close()

    # events of 3, 4, 2, 5, 1, 6 clusters: cut after 7, 7, 7, then the rest
    assert [len(chunk) for chunk in written] == [7, 7, 7]


def test_an_event_cannot_come_back_after_its_chunk(written, tmp_path):
    writer = root_writer.RootWriter(output_dir=tmp_path, chunk_size=2)
    writer.extend(clusters_of([((0, 1), 2), ((0, 2), 2)]))

    with pytest.raises(ValueError, match="contiguous"):
        writer.extend(clusters_of([((0, 1), 1)]))
