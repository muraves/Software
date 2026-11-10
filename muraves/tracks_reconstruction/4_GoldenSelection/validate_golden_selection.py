"""Cross-check golden_selection.py against an independent reference.

The reference is a plain per-event loop that follows
AnalysisOfCluster_and_tracks4planes.C line by line, reading the step-3 JSONL
output (where the nested lists, e.g. cluster_c4_index_xz[row][candidate] and
StripsEnergy_Z1[cluster][strip], are still nested). It therefore does not use
the flattened ROOT branches nor the BestTrack_4p_ClusterIndex_* shortcut that
golden_selection.py relies on.

Exit code 0 if every golden entry matches the reference, 1 otherwise.

Usage:
    python validate_golden_selection.py --jsonl MURAVES_AnalyzedData_run2500.jsonl \
        --golden Track4p_run2500.root [--min-events 1]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import awkward as ak
import uproot

PLANES = ("Z1", "Z2", "Z3", "Z4", "Y1", "Y2", "Y3", "Y4")


def reference_records(jsonl: Path) -> list[dict]:
    events = []
    with jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    # Run duration [min] from the event timestamps (Unix epoch in ms).
    stamps = [ev["timestamp"] for ev in events]
    run_duration = (max(stamps) - min(stamps)) / 60000.0 if stamps else -1.0

    records = []
    for ev in events:
        # Golden gate, as in the C++ macro.
        if ev["BestTrack_3p_ChiSquare_xz"] == -1 or ev["BestTrack_4p_ChiSquare_xz"] == -1:
            continue
        b_xz, b_xy = ev["BestTrack_3p_xz_index"], ev["BestTrack_3p_xy_index"]
        r_xz, r_xy = ev["Track_3p_of_4p_index_xz"], ev["Track_3p_of_4p_index_xy"]
        j_xz, j_xy = ev["Track_4p_index_xz"], ev["Track_4p_index_xy"]

        sel = {
            "Z1": ev["TrackCluster_z1_index"][b_xz],
            "Z2": ev["TrackCluster_z2_index"][b_xz],
            "Z3": ev["TrackCluster_z3_index"][b_xz],
            "Z4": int(ev["cluster_c4_index_xz"][r_xz][j_xz]),
            "Y1": ev["TrackCluster_y1_index"][b_xy],
            "Y2": ev["TrackCluster_y2_index"][b_xy],
            "Y3": ev["TrackCluster_y3_index"][b_xy],
            "Y4": int(ev["cluster_c4_index_xy"][r_xy][j_xy]),
        }
        rec = {
            "Phi": ev["Phi_4p"],
            "Theta": ev["Theta_4p"],
            "ChiSquare_3p_xz": ev["chiSquare_3p_xz"][b_xz],
            "ChiSquare_3p_xy": ev["chiSquare_3p_xy"][b_xy],
            "ChiSquare_xz": ev["chiSquare_4p_xz"][r_xz][j_xz],
            "Scattering_xz": ev["ScatteringAngle_xz"][r_xz][j_xz],
            "Scattering_xy": ev["ScatteringAngle_xy"][r_xy][j_xy],
            "ChiSquare_xy": ev["chiSquare_4p_xy"][r_xy][j_xy],
            "Run": ev["Run"],
            "TriggerRate": ev["TriggerRate"],
            "RunDuration": run_duration,
            "WorkingPoint": ev["WorkingPoint"],
            "Timestamp": ev["timestamp"],
        }
        for p in PLANES:
            c = sel[p]
            size = ev[f"ClusterSize_{p}"][c]
            rec[f"TrackClusterMaxStripEnergy_{p}"] = ev[f"StripsEnergy_{p}"][c][0]
            rec[f"TrackClusterMinStripEnergy_{p}"] = ev[f"StripsEnergy_{p}"][c][size - 1]
            rec[f"TrackClusterEnergy_{p}"] = ev[f"ClusterEnergy_{p}"][c]
            rec[f"TrackClusterPosition_{p}"] = ev[f"ClusterPosition_{p}"][c]
            rec[f"TrackClusterSize_{p}"] = size
            rec[f"TrackClusterExp_{p}"] = ev[f"Cluster{p}_Texp"][c]
            rec[f"ClusterMultriplicity_{p}"] = ev[f"Nclusters_{p}"]
            others = [i for i in range(ev[f"Nclusters_{p}"]) if i != c]
            rec[f"NonTrackClusterEnergy_{p}"] = [ev[f"ClusterEnergy_{p}"][i] for i in others]
            rec[f"NonTrackClusterPosition_{p}"] = [ev[f"ClusterPosition_{p}"][i] for i in others]
            rec[f"NonTrackClusterSize_{p}"] = [ev[f"ClusterSize_{p}"][i] for i in others]
        records.append(rec)
    return records


def _same(a, b) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-12)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jsonl", type=Path, required=True)
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--min-events", type=int, default=1,
                        help="Fail if fewer golden events than this are found.")
    args = parser.parse_args(argv)

    expected = reference_records(args.jsonl)
    with uproot.open(args.golden) as handle:
        got = ak.to_list(handle["Tracks4ptree"].arrays(library="ak"))

    errors = []
    if len(got) != len(expected):
        errors.append(f"entries: golden={len(got)} reference={len(expected)}")
    if len(expected) < args.min_events:
        errors.append(f"only {len(expected)} golden events (< {args.min_events})")

    for n, (g, e) in enumerate(zip(got, expected)):
        for key, value in e.items():
            if key not in g:
                errors.append(f"missing branch {key}")
                continue
            if not _same(g[key], value):
                errors.append(f"entry {n} branch {key}: golden={g[key]} reference={value}")
        if len(errors) > 20:
            break

    if errors:
        print("GOLDEN SELECTION VALIDATION FAILED:")
        for err in errors[:20]:
            print("  -", err)
        return 1
    print(f"Golden selection validated: {len(got)} entries, {len(expected[0]) if expected else 0} "
          f"branches checked against the reference loop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
