"""A1, B2, B5, B6: how the command-line tools write their outputs and
pick their inputs.

A1  every output is written in scratch and copied into place (as <name>.tmp,
    group permissions, atomic rename); nothing is ever written at the
    destination directly, and a failed run leaves nothing under its
    output names.
B2  clustering refuses chunks of the same prefix left in the output
    directory, or replaces them with --force; provenance goes only to
    this run's chunks.
B5  muraves-simGTrk's directory mode with --input-type, and the clustered
    and tracked versions of a chunk mapping to one golden file.
B6  directory inputs are chosen by the tree they hold, not by name.

No ROOT file is read or written: the ROOT writers, readers and the
reconstruction are replaced by fakes, so these tests run without uproot.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from muraves_lib import file_handler
from simReco_muraves.cli import common
from simReco_muraves.models.cluster_record import ClusterRecord


def mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture
def umask_022():
    """The usual umask, so that only an explicit chmod can give group write."""
    previous = os.umask(0o022)
    yield
    os.umask(previous)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(file_handler.time, "sleep", lambda seconds: None)


def scratch_folders(scratch_dir: Path) -> list[Path]:
    return sorted(scratch_dir.glob("muraves_scratch_*"))


# ----------------------------------------------------------------------
# muraves_lib.file_handler: the write path
# ----------------------------------------------------------------------

def test_scratch_to_output_copies_into_place_with_group_permissions(tmp_path, umask_022):
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    output = tmp_path / "out" / "x_tracked_part000.root"
    output.parent.mkdir()

    with file_handler.scratch_to_output(output, scratch_dir) as scratch_file:
        assert scratch_file.name == output.name
        assert scratch_file.parent.parent == scratch_dir
        scratch_file.write_bytes(b"payload")
        # Nothing at the destination while the file is being written.
        assert list(output.parent.iterdir()) == []

    assert output.read_bytes() == b"payload"
    assert mode(output) == file_handler.OUTPUT_FILE_MODE
    assert list(output.parent.iterdir()) == [output]  # no .tmp left
    assert scratch_folders(scratch_dir) == []


def test_scratch_to_output_follows_tmpdir_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(file_handler.tempfile, "tempdir", str(tmp_path))
    output = tmp_path / "x.root"

    with file_handler.scratch_to_output(output) as scratch_file:
        assert scratch_file.parent.parent == tmp_path
        scratch_file.write_bytes(b"payload")

    assert output.read_bytes() == b"payload"


def test_scratch_to_output_leaves_nothing_on_failure(tmp_path):
    output = tmp_path / "x.root"
    output.write_bytes(b"earlier output, being replaced")

    with pytest.raises(RuntimeError, match="reconstruction failed"):
        with file_handler.scratch_to_output(output, tmp_path) as scratch_file:
            scratch_file.write_bytes(b"half")
            raise RuntimeError("reconstruction failed")

    assert list(tmp_path.iterdir()) == []


def test_scratch_to_output_needs_a_written_file(tmp_path):
    output = tmp_path / "x.root"

    with pytest.raises(FileNotFoundError):
        with file_handler.scratch_to_output(output, tmp_path):
            pass

    assert list(tmp_path.iterdir()) == []


def test_copy_into_place_retries_a_failing_rename(tmp_path, monkeypatch, no_sleep):
    source = tmp_path / "source.root"
    source.write_bytes(b"payload")
    output = tmp_path / "out.root"
    real_replace = os.replace
    calls = []

    def flaky_replace(src, dst):
        calls.append(src)
        if len(calls) < 3:
            raise OSError("busy")
        real_replace(src, dst)

    monkeypatch.setattr(file_handler.os, "replace", flaky_replace)

    file_handler.copy_into_place(source, output)

    assert len(calls) == 3
    assert output.read_bytes() == b"payload"
    assert source.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.root", "source.root"]


def test_copy_into_place_gives_up_after_the_retries_and_cleans_up(tmp_path, monkeypatch, no_sleep):
    source = tmp_path / "source.root"
    source.write_bytes(b"payload")
    output = tmp_path / "out.root"
    calls = []

    def failing_replace(src, dst):
        calls.append(src)
        raise OSError("busy")

    monkeypatch.setattr(file_handler.os, "replace", failing_replace)

    with pytest.raises(OSError, match="busy"):
        file_handler.copy_into_place(source, output, retries=4)

    assert len(calls) == 4
    assert source.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["source.root"]


def test_make_output_dir_sets_the_mode_of_new_folders_only(tmp_path, umask_022):
    existing = tmp_path / "existing"
    existing.mkdir()
    os.chmod(existing, 0o755)

    made = file_handler.make_output_dir(existing / "a" / "b")

    assert made == existing / "a" / "b"
    assert mode(existing) == 0o755
    assert mode(existing / "a") == file_handler.OUTPUT_DIR_MODE
    assert mode(existing / "a" / "b") == file_handler.OUTPUT_DIR_MODE

    file_handler.make_output_dir(existing / "a" / "b")  # already there: fine


def test_make_output_dir_refuses_a_file(tmp_path):
    path = tmp_path / "file"
    path.write_text("")

    with pytest.raises(NotADirectoryError):
        file_handler.make_output_dir(path)


# ----------------------------------------------------------------------
# Provenance names the final path, not the scratch copy
# ----------------------------------------------------------------------

@pytest.fixture
def chains(monkeypatch):
    """The METADATA attach_provenance writes, by file, without ROOT."""
    from simReco_muraves import provenance
    from simReco_muraves.io import provenance_tree

    written = {}
    monkeypatch.setattr(provenance, "git_state", lambda: ("abc123", False))
    monkeypatch.setattr(provenance_tree, "read_chain", lambda path: [])

    def write_metadata(path, metadata):
        written[Path(path)] = metadata

    monkeypatch.setattr(provenance_tree, "write_metadata", write_metadata)
    return provenance_tree, written


def test_attach_provenance_records_the_final_path(chains, tmp_path):
    tree, written = chains
    scratch_file = tmp_path / "scratch" / "x.root"

    tree.attach_provenance(
        scratch_file, stage="tracking", detector="NERO", quiet=True, recorded_as="/pnfs/x.root"
    )

    assert written[scratch_file]["stages"][-1]["output_file"] == "/pnfs/x.root"
    assert written[scratch_file]["detector"] == "NERO"


def test_attach_provenance_to_many_records_one_final_path_each(chains, tmp_path):
    tree, written = chains
    chunks = [tmp_path / "a_part000.root", tmp_path / "a_part001.root"]
    final = [Path("/pnfs/a_part000.root"), Path("/pnfs/a_part001.root")]

    assert tree.attach_provenance_to_many(
        chunks, stage="clusterization", detector="BLU", recorded_as=final
    ) == 2

    assert [written[c]["stages"][-1]["output_file"] for c in chunks] == [str(f) for f in final]
    assert {written[c]["detector"] for c in chunks} == {"BLU"}

    with pytest.raises(ValueError):
        tree.attach_provenance_to_many(
            chunks, stage="clusterization", detector="BLU", recorded_as=final[:1]
        )


# ----------------------------------------------------------------------
# simReco_muraves.cli.common
# ----------------------------------------------------------------------

def default_tracked(path: Path) -> Path:
    return path.with_name(path.stem + "_tracked.root")


def test_prepare_output_refuses_an_existing_output_without_force(tmp_path):
    source = tmp_path / "x.root"
    source.write_text("")
    (tmp_path / "x_tracked.root").write_text("")

    with pytest.raises(FileExistsError):
        common.prepare_output(source, None, force=False, default_name=default_tracked)

    assert common.prepare_output(
        source, None, force=True, default_name=default_tracked
    ) == tmp_path / "x_tracked.root"


def test_prepare_output_refuses_to_replace_the_input(tmp_path):
    source = tmp_path / "x.root"
    source.write_text("")

    with pytest.raises(ValueError, match="replace the input"):
        common.prepare_output(source, source, force=True, default_name=default_tracked)


def test_prepare_output_creates_the_folder_group_writable(tmp_path, umask_022):
    source = tmp_path / "x.root"
    source.write_text("")

    output = common.prepare_output(
        source, tmp_path / "new" / "y.root", force=False, default_name=default_tracked
    )

    assert output == tmp_path / "new" / "y.root"
    assert mode(tmp_path / "new") == file_handler.OUTPUT_DIR_MODE


def test_scratch_dir_must_exist(tmp_path):
    assert common.checked_scratch_dir(None) is None
    assert common.checked_scratch_dir(tmp_path) == tmp_path.resolve()

    with pytest.raises(ValueError):
        common.checked_scratch_dir(tmp_path / "absent")


@pytest.fixture
def typed_folder(tmp_path, monkeypatch):
    """A folder whose files' types are given by the test, not by ROOT."""
    types = {}

    def make(name, kind):
        (tmp_path / name).write_text("")
        types[name] = kind

    def file_type(path):
        if types[path.name] == "broken":
            raise OSError("not a ROOT file")
        return types[path.name]

    monkeypatch.setattr(common, "root_file_type", file_type)
    return tmp_path, make


# ----------------------------------------------------------------------
# B6: inputs by tree, not by name
# ----------------------------------------------------------------------

def test_tracking_takes_clustered_files_by_tree_not_by_name(typed_folder):
    from simReco_muraves.cli import run_tracking

    folder, make = typed_folder
    make("simclustered_part000.root", "clustered")
    make("simclustered_part000_tracked.root", "tracked")  # an earlier output
    make("chunk_without_marker.root", "clustered")
    make("notes.txt", "unknown")

    assert [p.name for p in run_tracking.get_cluster_files(folder)] == [
        "chunk_without_marker.root",
        "simclustered_part000.root",
    ]


def test_a_file_that_cannot_be_read_is_an_error(typed_folder):
    folder, make = typed_folder
    make("a_clustered_part000.root", "broken")

    with pytest.raises(ValueError, match="cannot read a_clustered_part000.root"):
        common.select_by_type(folder, {"clustered"})


# ----------------------------------------------------------------------
# B5: muraves-simGTrk's directory mode
# ----------------------------------------------------------------------

@pytest.fixture
def golden(typed_folder, monkeypatch):
    from simReco_muraves.cli import run_gTrks

    folder, make = typed_folder
    for name, kind in (
        ("x_clustered_part000.root", "clustered"),
        ("x_clustered_part001.root", "clustered"),
        ("x_tracked_part000.root", "tracked"),
        ("x_tracked_part001.root", "tracked"),
        ("x_golden_part009.root", "golden"),
    ):
        make(name, kind)

    monkeypatch.setattr(run_gTrks, "root_file_type", common.root_file_type)

    processed = []

    def fake(route):
        def process(input_file, **options):
            processed.append((route, input_file.name))
        return process

    monkeypatch.setattr(run_gTrks, "process_tracked_file", fake("tracked"))
    monkeypatch.setattr(run_gTrks, "process_clustered_file", fake("clustered"))
    return run_gTrks, folder, processed


def test_golden_input_type_selects_the_files_of_that_type(golden):
    run_gTrks, folder, processed = golden

    run_gTrks.main([str(folder), "--input-type", "tracked"])

    assert processed == [
        ("tracked", "x_tracked_part000.root"),
        ("tracked", "x_tracked_part001.root"),
    ]


def test_golden_auto_refuses_two_inputs_for_one_output(golden):
    run_gTrks, folder, processed = golden

    with pytest.raises(SystemExit, match="x_golden_part000.root"):
        run_gTrks.main([str(folder)])

    assert processed == []


def test_golden_type_mismatch_is_an_ordinary_error(golden):
    run_gTrks, folder, _ = golden

    with pytest.raises(ValueError, match="--input-type tracked"):
        run_gTrks.resolve_input_type(folder / "x_clustered_part000.root", "tracked")


# ----------------------------------------------------------------------
# A1 for one-file stages: tracking and golden write through scratch
# ----------------------------------------------------------------------

def test_tracking_writes_through_scratch(tmp_path, monkeypatch):
    from simReco_muraves.cli import run_tracking

    source = tmp_path / "x_NERO_clustered_part000.root"
    source.write_text("")
    output = tmp_path / "tracked" / "x_NERO_tracked_part000.root"
    seen = {}

    monkeypatch.setattr(run_tracking, "detector_for", lambda files, given: "NERO")
    monkeypatch.setattr(run_tracking, "load_clusters", lambda path: ["cluster"])
    monkeypatch.setattr(run_tracking, "build_tracking_events", lambda clusters: ["event"])
    monkeypatch.setattr(run_tracking, "run_tracking_pipeline", lambda clusters, **kw: ["result"])
    monkeypatch.setattr(run_tracking, "build_tracked_event_record", lambda e, r: "record")
    monkeypatch.setattr(run_tracking, "write_tracked_root", lambda path, records: Path(path).write_bytes(b"tracked"))

    def attach(path, **kw):
        seen["written"] = Path(path)
        seen["recorded_as"] = kw["recorded_as"]
        seen["detector"] = kw["detector"]
        seen["depth_correction_applied"] = kw["parameters"]["depth_correction_applied"]
        seen["destination_empty"] = not output.exists()
        return {}

    monkeypatch.setattr(run_tracking, "attach_provenance", attach)

    run_tracking.process_file(source, output_file=output, scratch_dir=tmp_path)

    assert seen["written"] != output and seen["written"].name == output.name
    assert seen["recorded_as"] == output
    assert seen["detector"] == "NERO"
    assert seen["depth_correction_applied"] is False
    assert seen["destination_empty"]
    assert output.read_bytes() == b"tracked"
    assert mode(output) == file_handler.OUTPUT_FILE_MODE
    assert scratch_folders(tmp_path) == []


@pytest.fixture
def golden_tracked_route(tmp_path, monkeypatch):
    from simReco_muraves.cli import run_gTrks

    source = tmp_path / "x_NERO_tracked_part000.root"
    source.write_text("")
    output = tmp_path / "golden" / "x_NERO_golden_part000.root"
    seen = {}

    monkeypatch.setattr(run_gTrks, "detector_for", lambda files, given: "NERO")

    def run_golden(*, tracked_root_file, output_file):
        Path(output_file).write_bytes(b"golden")
        return Path(output_file)

    monkeypatch.setattr(run_gTrks, "run_golden_tracking_from_tracked", run_golden)
    monkeypatch.setattr(
        run_gTrks, "attach_provenance",
        lambda path, **kw: seen.setdefault("recorded_as", kw["recorded_as"]) is not None,
    )
    return run_gTrks, source, output, seen


def test_golden_checks_its_output_in_scratch_before_the_copy(golden_tracked_route, monkeypatch, tmp_path):
    run_gTrks, source, output, seen = golden_tracked_route

    def inspect(path):
        seen["inspected"] = path
        assert not output.exists()

    monkeypatch.setattr(run_gTrks, "inspect_output", inspect)

    run_gTrks.process_tracked_file(source, output_file=output, scratch_dir=tmp_path)

    assert seen["inspected"] != output and seen["inspected"].name == output.name
    assert seen["recorded_as"] == output
    assert output.read_bytes() == b"golden"
    assert mode(output) == file_handler.OUTPUT_FILE_MODE


def test_golden_leaves_no_output_when_the_check_fails(golden_tracked_route, monkeypatch, tmp_path):
    run_gTrks, source, output, _ = golden_tracked_route

    def inspect(path):
        raise RuntimeError("Golden ROOT output is incomplete")

    monkeypatch.setattr(run_gTrks, "inspect_output", inspect)

    with pytest.raises(RuntimeError, match="incomplete"):
        run_gTrks.process_tracked_file(source, output_file=output, scratch_dir=tmp_path)

    assert not output.exists()
    assert list(output.parent.iterdir()) == []
    assert scratch_folders(tmp_path) == []


# ----------------------------------------------------------------------
# A1 and B2 for clustering
# ----------------------------------------------------------------------

def test_root_writer_needs_an_existing_folder(tmp_path):
    from simReco_muraves.io.root_writer import RootWriter

    with pytest.raises(NotADirectoryError):
        RootWriter(output_dir=tmp_path / "absent")

    with pytest.raises(TypeError):
        RootWriter()


class FakeReader:
    """Three events with hits; the clustering below is faked too."""

    opened = []

    def __init__(self, filename):
        FakeReader.opened.append(filename)

    def get_event_keys(self):
        return [(0, 1), (0, 2), (0, 3)]

    def read_event(self, process_id, event_id):
        return ["hit"]


@pytest.fixture
def clustering(tmp_path, monkeypatch):
    """muraves-simCluster with the reading, digitization, clustering and
    ROOT writing faked: each event gives two clusters, and a chunk file
    holds the events it contains as text."""
    from simReco_muraves.cli import run_clusterization as cli
    from simReco_muraves.io import root_writer

    FakeReader.opened = []
    seen = {}

    monkeypatch.setattr(cli, "RootReader", FakeReader)
    monkeypatch.setattr(cli, "aggregate_bar_hits", lambda hits: hits)
    monkeypatch.setattr(cli, "build_planes", lambda hits: [SimpleNamespace(station=8)])

    class Digitizer:
        def digitize(self, hits):
            if seen.get("fail"):
                raise RuntimeError("digitization failed")
            return hits

    monkeypatch.setattr(cli, "make_digitizer", lambda setup, seed: Digitizer())

    class Clusterizer:
        def __init__(self, rng_seed):
            pass

        def cluster_plane(self, plane):
            return None

    monkeypatch.setattr(cli, "SimClusterizer", Clusterizer)

    def records(*, event, station, cluster_collection, plane):
        return [
            ClusterRecord(
                process_id=0, event=event, station=station, cluster_id=i,
                cluster_multiplicity=2, cluster_energy=20.0, cluster_position=0.0,
                cluster_size=1, cluster_time=5.0, cluster_time_spread=0.0,
                strip_ids=[10], strip_energies=[20.0],
            )
            for i in range(2)
        ]

    monkeypatch.setattr(cli, "cluster_collection_to_records", records)

    class TextFile:
        def __init__(self, path):
            self.path = Path(path)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __setitem__(self, name, data):
            self.path.write_text(f"{name} {sorted(set(data['Event']))}")

    monkeypatch.setattr(
        root_writer.RootWriter, "_build_tree_data",
        lambda self: {"Event": list(self.event)},
    )
    monkeypatch.setattr(root_writer.uproot, "recreate", TextFile)

    def attach_to_many(paths, **options):
        destination = seen["destination"]
        seen["provenance_files"] = list(paths)
        seen["recorded_as"] = list(options["recorded_as"])
        seen["parameters"] = options["parameters"]
        seen["detector"] = options["detector"]
        seen["extra_files"] = list(options["extra_files"])
        seen["in_scratch"] = all(p.is_file() and p.parent != destination for p in paths)
        seen["destination_then"] = sorted(q.name for q in destination.iterdir())
        return len(paths)

    monkeypatch.setattr(cli, "attach_provenance_to_many", attach_to_many)

    source = tmp_path / "hits.root"
    source.write_text("")
    destination = tmp_path / "clustered"
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir()
    seen["destination"] = destination

    def run(*extra):
        cli.main([
            str(source), "--detector", "NERO", "-o", str(destination),
            "--scratch-dir", str(scratch_dir), "--chunk-size", "2",
            "--progress-every", "0", *extra,
        ])

    return SimpleNamespace(
        run=run, seen=seen, destination=destination, scratch_dir=scratch_dir,
        prefix="hits_NERO_clustered", cli=cli,
    )


def chunk_names(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir())


def test_clustering_writes_its_chunks_in_scratch_and_copies_them_at_the_end(clustering, umask_022):
    clustering.run()

    names = [f"{clustering.prefix}_part{i:03d}.root" for i in range(3)]
    seen = clustering.seen
    assert seen["in_scratch"]
    assert seen["destination_then"] == []
    assert [p.name for p in seen["provenance_files"]] == names
    assert seen["recorded_as"] == [clustering.destination / name for name in names]
    assert seen["parameters"]["events_processed"] == 3
    assert seen["parameters"]["total_clusters"] == 6
    assert seen["detector"] == "NERO"
    assert seen["extra_files"] == []  # energy method: no calibration file

    assert chunk_names(clustering.destination) == names
    for name in names:
        assert mode(clustering.destination / name) == file_handler.OUTPUT_FILE_MODE
    assert mode(clustering.destination) == file_handler.OUTPUT_DIR_MODE
    assert scratch_folders(clustering.scratch_dir) == []


def test_clustering_records_the_calibration_file_it_used(clustering):
    from simReco_muraves.detector import packaged_calibration_file

    clustering.run("--pe-per-cm-file", "--run-range", "5710-5759")

    assert clustering.seen["extra_files"] == [str(packaged_calibration_file().resolve())]


def test_clustering_refuses_chunks_left_in_the_output_directory(clustering):
    clustering.destination.mkdir()
    (clustering.destination / f"{clustering.prefix}_part007.root").write_text("old")

    with pytest.raises(SystemExit, match="--force"):
        clustering.run()

    assert FakeReader.opened == []
    assert chunk_names(clustering.destination) == [f"{clustering.prefix}_part007.root"]


def test_clustering_force_replaces_the_chunks_of_its_prefix_only(clustering):
    clustering.destination.mkdir()
    for i in range(5):
        (clustering.destination / f"{clustering.prefix}_part{i:03d}.root").write_text("old")
    (clustering.destination / "other_NERO_clustered_part000.root").write_text("other")

    clustering.run("--force")

    assert chunk_names(clustering.destination) == [
        f"{clustering.prefix}_part000.root",
        f"{clustering.prefix}_part001.root",
        f"{clustering.prefix}_part002.root",
        "other_NERO_clustered_part000.root",
    ]
    assert (clustering.destination / f"{clustering.prefix}_part000.root").read_text() != "old"
    assert len(clustering.seen["provenance_files"]) == 3


def test_a_failed_clustering_leaves_no_chunk_of_its_prefix(clustering):
    clustering.destination.mkdir()
    (clustering.destination / f"{clustering.prefix}_part000.root").write_text("old")
    (clustering.destination / "other_NERO_clustered_part000.root").write_text("other")
    clustering.seen["fail"] = True

    with pytest.raises(RuntimeError, match="digitization failed"):
        clustering.run("--force")

    assert chunk_names(clustering.destination) == ["other_NERO_clustered_part000.root"]
    assert scratch_folders(clustering.scratch_dir) == []
