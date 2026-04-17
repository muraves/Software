#!/usr/bin/env python3
"""Event-level ROOT debug tool for branch-by-branch mismatch diagnosis.

This script compares event content between a C++ ROOT and a Python ROOT file,
with focus on jagged branches such as StripsID_*.

It reports:
- exact equality per event
- multiset equality per event (order-insensitive)
- cardinality differences
- first mismatch examples with compact value-count deltas
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from typing import Any


DISPLACEMENT_CORE_BRANCHES = {
    "displacement_p4_xz",
    "displacement_p4_xy",
}


def _related_displacement_branches(axis: str) -> list[str]:
    return [
        f"ExpectedPosition_OnPlane4th_{axis}",
        f"cluster_c4_index_{axis}",
        f"Track_3p_of_4p_index_{axis}",
        f"Track_4p_index_{axis}",
        f"Best_track_4p_isTexpNULL_{axis}",
        f"ScatteringAngle_{axis}",
        f"chiSquare_4p_{axis}",
    ]


def _strip_cycle(name: str) -> str:
    return name.split(";", maxsplit=1)[0]


def _find_ttrees(file_obj: Any) -> dict[str, Any]:
    trees: dict[str, Any] = {}
    for raw_key, class_name in file_obj.classnames(recursive=True).items():
        if not class_name.startswith("TTree"):
            continue
        trees[_strip_cycle(raw_key)] = file_obj[raw_key]
    return trees


def _flatten_value(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        out: list[Any] = []
        for item in value:
            out.extend(_flatten_value(item))
        return out
    return [value]


def _shape_signature(value: Any) -> Any:
    """Return a structure-only signature (ignores scalar values)."""
    if isinstance(value, (list, tuple)):
        return [_shape_signature(item) for item in value]
    return "v"


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float, bool)) and not isinstance(value, complex)


def _values_equal(a: Any, b: Any, tol: float) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y, tol) for x, y in zip(a, b))

    if _is_numeric(a) and _is_numeric(b):
        if isinstance(a, bool) or isinstance(b, bool):
            return bool(a) == bool(b)
        fa = float(a)
        fb = float(b)
        if math.isnan(fa) and math.isnan(fb):
            return True
        return abs(fa - fb) <= tol

    return a == b


def _multiset_equal(a: Any, b: Any, np_module: Any, tol: float) -> bool:
    flat_a = _flatten_value(a)
    flat_b = _flatten_value(b)
    if len(flat_a) != len(flat_b):
        return False

    if all(_is_numeric(v) for v in flat_a) and all(_is_numeric(v) for v in flat_b):
        arr_a = np_module.asarray(flat_a, dtype=np_module.float64)
        arr_b = np_module.asarray(flat_b, dtype=np_module.float64)
        arr_a = np_module.sort(arr_a)
        arr_b = np_module.sort(arr_b)
        return bool(np_module.allclose(arr_a, arr_b, atol=tol, rtol=0.0, equal_nan=True))

    return sorted(str(v) for v in flat_a) == sorted(str(v) for v in flat_b)


def _value_count_diff(a: Any, b: Any, top_n: int = 10) -> list[dict[str, Any]]:
    flat_a = [v for v in _flatten_value(a) if _is_numeric(v)]
    flat_b = [v for v in _flatten_value(b) if _is_numeric(v)]

    if not flat_a and not flat_b:
        return []

    # Rounded keys make tiny floating eps easier to read in diffs.
    cnt_a = Counter(round(float(v), 6) for v in flat_a)
    cnt_b = Counter(round(float(v), 6) for v in flat_b)

    out: list[dict[str, Any]] = []
    for key in sorted(set(cnt_a) | set(cnt_b)):
        a_count = cnt_a.get(key, 0)
        b_count = cnt_b.get(key, 0)
        if a_count != b_count:
            out.append(
                {
                    "value": key,
                    "cpp_count": a_count,
                    "python_count": b_count,
                    "delta": a_count - b_count,
                }
            )

    out.sort(key=lambda row: abs(int(row["delta"])), reverse=True)
    return out[:top_n]


def _parse_selector(selector: str) -> tuple[str | None, str]:
    # Format supported: "branch" or "tree:branch"
    if ":" in selector:
        tree, branch = selector.split(":", maxsplit=1)
        return tree, branch
    return None, selector


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Event-level debug for ROOT branches (C++ vs Python)."
    )
    parser.add_argument("cpp_root", type=Path, help="ROOT file from C++ reconstruction")
    parser.add_argument("python_root", type=Path, help="ROOT file from Python reconstruction")
    parser.add_argument(
        "--branch",
        action="append",
        default=None,
        help=(
            "Branch selector to debug. Repeatable. Format: 'branch' or 'tree:branch'. "
            "Example: --branch StripsID_Z1"
        ),
    )
    parser.add_argument(
        "--auto-stripsid",
        action="store_true",
        help="Auto-select all common branches containing 'StripsID'.",
    )
    parser.add_argument(
        "--displacement-debug",
        action="store_true",
        help=(
            "Auto-select displacement branches and attach 4p-track context in mismatch examples "
            "(ExpectedPosition_OnPlane4th, cluster_c4_index, Track_3p_of_4p_index, "
            "Track_4p_index, Best_track_4p_isTexpNULL, ScatteringAngle, chiSquare_4p)."
        ),
    )
    parser.add_argument(
        "--tree",
        action="append",
        default=None,
        help="Optional tree filter. Repeatable.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=10,
        help="Maximum mismatch examples saved per branch.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.0,
        help="Absolute tolerance for numeric equality.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path. Default: debug_<cpp>_vs_<python>.json",
    )
    return parser


def main() -> int:
    args = _make_parser().parse_args()

    import importlib

    np = importlib.import_module("numpy")
    uproot = importlib.import_module("uproot")
    ak = importlib.import_module("awkward")

    if not args.cpp_root.exists():
        raise FileNotFoundError(f"Missing C++ ROOT file: {args.cpp_root}")
    if not args.python_root.exists():
        raise FileNotFoundError(f"Missing Python ROOT file: {args.python_root}")

    if args.output is None:
        out_name = f"debug_{args.cpp_root.stem}_vs_{args.python_root.stem}.json"
        args.output = Path.cwd() / out_name

    report: dict[str, Any] = {
        "cpp_root": str(args.cpp_root),
        "python_root": str(args.python_root),
        "tolerance": float(max(0.0, args.tolerance)),
        "max_examples": int(max(1, args.max_examples)),
        "displacement_debug": bool(args.displacement_debug),
        "branches": [],
    }

    selectors = list(args.branch or [])

    with uproot.open(args.cpp_root) as cpp_file, uproot.open(args.python_root) as py_file:
        cpp_trees = _find_ttrees(cpp_file)
        py_trees = _find_ttrees(py_file)

        common_trees = sorted(set(cpp_trees) & set(py_trees))
        if args.tree:
            wanted = set(args.tree)
            common_trees = [tree for tree in common_trees if tree in wanted]

        # Auto-add StripsID branches if requested.
        if args.auto_stripsid:
            auto_select: set[str] = set()
            for tree_name in common_trees:
                cpp_branches = set(cpp_trees[tree_name].keys())
                py_branches = set(py_trees[tree_name].keys())
                for branch in sorted(cpp_branches & py_branches):
                    if "stripsid" in branch.lower():
                        auto_select.add(f"{tree_name}:{branch}")
            selectors.extend(sorted(auto_select))

        if args.displacement_debug:
            disp_select: set[str] = set()
            for tree_name in common_trees:
                cpp_branches = set(cpp_trees[tree_name].keys())
                py_branches = set(py_trees[tree_name].keys())
                common_branches = cpp_branches & py_branches

                for branch in sorted(common_branches):
                    if branch in DISPLACEMENT_CORE_BRANCHES:
                        disp_select.add(f"{tree_name}:{branch}")

                for axis in ("xz", "xy"):
                    for related in _related_displacement_branches(axis):
                        if related in common_branches:
                            disp_select.add(f"{tree_name}:{related}")
            selectors.extend(sorted(disp_select))

        if not selectors:
            raise ValueError("No branches selected. Use --branch and/or --auto-stripsid.")

        targets: list[tuple[str, str]] = []
        for selector in selectors:
            sel_tree, sel_branch = _parse_selector(selector)
            for tree_name in common_trees:
                if sel_tree is not None and tree_name != sel_tree:
                    continue
                cpp_tree = cpp_trees[tree_name]
                py_tree = py_trees[tree_name]
                if sel_branch in cpp_tree.keys() and sel_branch in py_tree.keys():
                    targets.append((tree_name, sel_branch))

        # Deduplicate while preserving order.
        seen: set[tuple[str, str]] = set()
        unique_targets: list[tuple[str, str]] = []
        for target in targets:
            if target in seen:
                continue
            seen.add(target)
            unique_targets.append(target)

        if not unique_targets:
            raise ValueError("No matching common branches found for the provided selectors.")

        for tree_name, branch in unique_targets:
            cpp_values = ak.to_list(cpp_trees[tree_name][branch].array(library="ak"))
            py_values = ak.to_list(py_trees[tree_name][branch].array(library="ak"))

            related_cpp_values: dict[str, list[Any]] = {}
            related_py_values: dict[str, list[Any]] = {}
            if args.displacement_debug and branch in DISPLACEMENT_CORE_BRANCHES:
                axis = "xz" if branch.endswith("_xz") else "xy"
                for related in _related_displacement_branches(axis):
                    if related in cpp_trees[tree_name].keys() and related in py_trees[tree_name].keys():
                        related_cpp_values[related] = ak.to_list(
                            cpp_trees[tree_name][related].array(library="ak")
                        )
                        related_py_values[related] = ak.to_list(
                            py_trees[tree_name][related].array(library="ak")
                        )

            n_cpp_events = len(cpp_values)
            n_py_events = len(py_values)
            n_compared = min(n_cpp_events, n_py_events)

            exact_equal = 0
            multiset_equal = 0
            shape_mismatch_only = 0
            order_mismatch_only = 0
            content_mismatch = 0
            examples: list[dict[str, Any]] = []

            for idx in range(n_compared):
                cpp_v = cpp_values[idx]
                py_v = py_values[idx]

                is_exact = _values_equal(cpp_v, py_v, report["tolerance"])
                if is_exact:
                    exact_equal += 1
                    multiset_equal += 1
                    continue

                flat_equal = _values_equal(
                    _flatten_value(cpp_v),
                    _flatten_value(py_v),
                    report["tolerance"],
                )

                is_multiset = _multiset_equal(cpp_v, py_v, np, report["tolerance"])
                if is_multiset:
                    multiset_equal += 1

                if flat_equal:
                    mismatch_kind = "shape_only"
                    shape_mismatch_only += 1
                elif is_multiset:
                    mismatch_kind = "order_only"
                    order_mismatch_only += 1
                else:
                    mismatch_kind = "content"
                    content_mismatch += 1

                if len(examples) < report["max_examples"]:
                    context: dict[str, Any] = {}
                    if related_cpp_values:
                        for related_name, related_arr in related_cpp_values.items():
                            if idx < len(related_arr) and idx < len(related_py_values.get(related_name, [])):
                                context[related_name] = {
                                    "cpp": related_arr[idx],
                                    "python": related_py_values[related_name][idx],
                                }

                    examples.append(
                        {
                            "event_index": idx,
                            "mismatch_kind": mismatch_kind,
                            "exact_equal": is_exact,
                            "flat_equal": flat_equal,
                            "multiset_equal": is_multiset,
                            "cpp_flat_len": len(_flatten_value(cpp_v)),
                            "python_flat_len": len(_flatten_value(py_v)),
                            "cpp_shape": _shape_signature(cpp_v),
                            "python_shape": _shape_signature(py_v),
                            "top_value_count_diff": _value_count_diff(cpp_v, py_v),
                            "cpp_value": cpp_v,
                            "python_value": py_v,
                            "displacement_context": context,
                        }
                    )

            branch_report = {
                "tree": tree_name,
                "branch": branch,
                "n_cpp_events": n_cpp_events,
                "n_python_events": n_py_events,
                "n_compared_events": n_compared,
                "n_exact_equal_events": exact_equal,
                "n_multiset_equal_events": multiset_equal,
                "n_exact_mismatch_events": n_compared - exact_equal,
                "n_content_mismatch_events": n_compared - multiset_equal,
                "n_shape_mismatch_only_events": shape_mismatch_only,
                "n_order_mismatch_only_events": order_mismatch_only,
                "n_real_content_mismatch_events": content_mismatch,
                "examples": examples,
            }
            report["branches"].append(branch_report)

    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(f"Debug report: {args.output}")
    print(f"Compared branches: {len(report['branches'])}")
    for row in report["branches"]:
        print(
            f"  {row['tree']}/{row['branch']}: "
            f"exact_mismatch={row['n_exact_mismatch_events']}, "
            f"shape_only={row['n_shape_mismatch_only_events']}, "
            f"order_only={row['n_order_mismatch_only_events']}, "
            f"real_content={row['n_real_content_mismatch_events']}, "
            f"events={row['n_compared_events']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
