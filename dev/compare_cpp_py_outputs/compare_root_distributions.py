#!/usr/bin/env python3
"""Compare branch distributions between two ROOT files.

This script scans all common TTrees and branches in two ROOT files (for example
C++ vs Python reconstruction outputs), runs a two-sample Kolmogorov-Smirnov
(KS) test on numeric branches, and writes machine-readable reports.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

np = None
uproot = None
ak = None
scipy_ks_2samp = None


@dataclass
class KSResult:
    tree: str
    branch: str
    n_cpp: int
    n_python: int
    ks_statistic: float
    p_value: float
    cpp_mean: float
    py_mean: float
    cpp_std: float
    py_std: float
    cpp_median: float
    py_median: float
    abs_mean_diff: float
    ks_effect_label: str
    significant: bool
    note: str


def _strip_cycle(name: str) -> str:
    """Normalize ROOT keys by removing the ;cycle suffix."""
    return name.split(";", maxsplit=1)[0]


def _find_ttrees(file_obj: Any) -> dict[str, Any]:
    """Return all TTrees in the file as a path -> tree mapping."""
    trees: dict[str, Any] = {}
    for raw_key, class_name in file_obj.classnames(recursive=True).items():
        if not class_name.startswith("TTree"):
            continue
        clean_key = _strip_cycle(raw_key)
        trees[clean_key] = file_obj[raw_key]
    return trees


def _array_from_branch(tree: Any, branch_name: str) -> Any:
    """Read and flatten a ROOT branch into a 1D NumPy array."""
    array = tree[branch_name].array(library="ak")

    # Flatten nested/jagged content while keeping scalar branches unchanged.
    ndim = getattr(array, "ndim", 1)
    if ndim > 1:
        array = ak.flatten(array, axis=None)

    try:
        np_array = ak.to_numpy(array)
    except Exception:  # noqa: BLE001
        np_array = np.asarray(array)

    if np_array.ndim > 1:
        np_array = np_array.reshape(-1)

    return np_array


def _is_numeric(arr: Any) -> bool:
    if arr.dtype == object:
        return False
    return bool(np.issubdtype(arr.dtype, np.number) or np.issubdtype(arr.dtype, np.bool_))


def _finite_only(arr: Any) -> Any:
    if np.issubdtype(arr.dtype, np.bool_):
        return arr.astype(np.float64)
    return arr[np.isfinite(arr)]


def _ks_pvalue_asymptotic(d_stat: float, n1: int, n2: int) -> float:
    """Asymptotic p-value approximation for two-sample KS test."""
    if n1 <= 0 or n2 <= 0:
        return float("nan")
    en = math.sqrt((n1 * n2) / (n1 + n2))
    lam = (en + 0.12 + 0.11 / en) * d_stat

    # Smirnov series approximation.
    s = 0.0
    for j in range(1, 200):
        term = ((-1) ** (j - 1)) * math.exp(-2.0 * (j**2) * (lam**2))
        s += term
        if abs(term) < 1e-12:
            break

    p = max(0.0, min(1.0, 2.0 * s))
    return p


def _ks_2samp(x: Any, y: Any) -> tuple[float, float]:
    """Compute KS statistic and p-value.

    Uses SciPy when available; otherwise uses a NumPy + asymptotic fallback.
    """
    if scipy_ks_2samp is not None:
        result = scipy_ks_2samp(x, y, alternative="two-sided", method="auto")
        return float(result.statistic), float(result.pvalue)

    x_sorted = np.sort(x)
    y_sorted = np.sort(y)
    values = np.sort(np.concatenate([x_sorted, y_sorted]))

    cdf_x = np.searchsorted(x_sorted, values, side="right") / x_sorted.size
    cdf_y = np.searchsorted(y_sorted, values, side="right") / y_sorted.size

    d_stat = float(np.max(np.abs(cdf_x - cdf_y)))
    p_value = _ks_pvalue_asymptotic(d_stat, x_sorted.size, y_sorted.size)
    return d_stat, p_value


def _summarize(arr: Any) -> tuple[float, float, float]:
    return float(np.mean(arr)), float(np.std(arr)), float(np.median(arr))


def _ks_effect_label(d_stat: float) -> str:
    """Classify KS statistic magnitude with practical thresholds."""
    if d_stat < 0.02:
        return "very_small"
    if d_stat < 0.05:
        return "small"
    if d_stat < 0.10:
        return "moderate"
    return "large"


def _is_identifier_like(branch_name: str) -> bool:
    upper = branch_name.upper()
    return "ID" in upper or "INDEX" in upper


def _is_physics_like(branch_name: str) -> bool:
    lower = branch_name.lower()
    keywords = ("angle", "chi", "residue", "displacement", "slope", "intercept")
    return any(key in lower for key in keywords)


def _build_impact_report(rows: list[KSResult], alpha: float) -> dict[str, Any]:
    total = len(rows)
    significant = [row for row in rows if row.significant]
    non_identifier = [row for row in rows if not _is_identifier_like(row.branch)]
    non_identifier_significant = [
        row for row in non_identifier if row.significant
    ]
    physics_like = [row for row in rows if _is_physics_like(row.branch)]
    physics_like_significant = [row for row in physics_like if row.significant]

    sig_fraction = (len(significant) / total) if total > 0 else 0.0
    non_id_sig_fraction = (
        len(non_identifier_significant) / len(non_identifier)
        if non_identifier
        else 0.0
    )

    if non_id_sig_fraction <= 0.05 and len(physics_like_significant) == 0:
        impact = "PASS"
        interpretation = "Differences appear mostly limited to indexing/ordering-style branches."
    elif non_id_sig_fraction <= 0.15 and len(physics_like_significant) <= 3:
        impact = "WARN"
        interpretation = "Some differences affect non-identifier branches; validate downstream selections."
    else:
        impact = "ALERT"
        interpretation = "Differences likely impact physics-facing quantities or selections."

    top_non_identifier = sorted(non_identifier_significant, key=lambda r: r.p_value)[:10]
    top_physics_like = sorted(physics_like_significant, key=lambda r: r.p_value)[:10]

    return {
        "alpha": alpha,
        "impact_level": impact,
        "interpretation": interpretation,
        "counts": {
            "total_compared": total,
            "significant": len(significant),
            "non_identifier_total": len(non_identifier),
            "non_identifier_significant": len(non_identifier_significant),
            "physics_like_total": len(physics_like),
            "physics_like_significant": len(physics_like_significant),
        },
        "fractions": {
            "significant_fraction": sig_fraction,
            "non_identifier_significant_fraction": non_id_sig_fraction,
        },
        "top_non_identifier_significant": [asdict(row) for row in top_non_identifier],
        "top_physics_like_significant": [asdict(row) for row in top_physics_like],
    }


def _write_csv(path: Path, rows: list[KSResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()) if rows else [])
        if rows:
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))


def _safe_plot_name(tree: str, branch: str) -> str:
    tree_clean = tree.replace("/", "__")
    branch_clean = branch.replace("/", "__")
    return f"{tree_clean}__{branch_clean}.png"


def _branch_matches_any_pattern(branch_name: str, patterns: list[str]) -> bool:
    """Return True if branch_name matches any wildcard pattern (case-insensitive)."""
    branch_lower = branch_name.lower()
    for pattern in patterns:
        if fnmatch.fnmatch(branch_lower, pattern.lower()):
            return True
    return False


def _raw_branch_array(tree: Any, branch_name: str) -> Any:
    """Read a ROOT branch without flattening so event structure is preserved."""
    return tree[branch_name].array(library="ak")


def _flatten_event_values(value: Any) -> list[float]:
    """Recursively flatten one event payload into numeric values."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        flattened: list[float] = []
        for item in value:
            flattened.extend(_flatten_event_values(item))
        return flattened
    try:
        return [float(value)]
    except (TypeError, ValueError):
        return []


def _event_has_single_strip(value: Any) -> bool:
    """Return True when an event payload contains at least one cluster of size 1."""
    return any(math.isclose(entry, 1.0, rel_tol=0.0, abs_tol=0.0) for entry in _flatten_event_values(value))


def _extract_displacement_subset(
    tree: Any,
    displacement_branch: str,
    cluster_size_branches: list[str],
    include_single_strip: bool,
) -> Any:
    """Return flattened displacement values from events split by single-strip presence."""
    displacement_events = ak.to_list(_raw_branch_array(tree, displacement_branch))
    cluster_size_events = [ak.to_list(_raw_branch_array(tree, branch)) for branch in cluster_size_branches]

    selected_values: list[float] = []
    for event_index, event_displacement in enumerate(displacement_events):
        has_single_strip = any(
            _event_has_single_strip(branch_events[event_index])
            for branch_events in cluster_size_events
        )
        if has_single_strip != include_single_strip:
            continue
        selected_values.extend(_flatten_event_values(event_displacement))

    return np.asarray(selected_values, dtype=np.float64)


def _plot_array_pair(
    cpp_arr: Any,
    py_arr: Any,
    title: str,
    out_path: Path,
    plt: Any,
) -> bool:
    """Plot two 1D arrays with an overlay and pull-style residual panel."""
    if cpp_arr.size == 0 or py_arr.size == 0:
        return False

    combined = np.concatenate([cpp_arr, py_arr])
    if combined.size == 0:
        return False

    min_v = float(np.min(combined))
    max_v = float(np.max(combined))
    if min_v == max_v:
        eps = 1e-9 if min_v == 0 else abs(min_v) * 1e-6
        bins = np.array([min_v - eps, max_v + eps], dtype=np.float64)
    else:
        bins = np.histogram_bin_edges(combined, bins="auto")
        if bins.size > 200:
            bins = np.histogram_bin_edges(combined, bins=200)

    n_cpp_plot = int(cpp_arr.size)
    n_py_plot = int(py_arr.size)

    fig, (ax, ax_res) = plt.subplots(
        2, 1, figsize=(8, 8), dpi=120,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    hist_cpp, bin_edges = np.histogram(cpp_arr, bins=bins, density=False)
    hist_py, _ = np.histogram(py_arr, bins=bins, density=False)

    ax.hist(
        cpp_arr,
        bins=bins,
        histtype="step",
        density=False,
        linewidth=1.5,
        label=f"C++ (entries={n_cpp_plot})",
    )
    ax.hist(
        py_arr,
        bins=bins,
        histtype="step",
        density=False,
        linewidth=1.5,
        label=f"Python (entries={n_py_plot})",
    )
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("Counts")
    ax.legend()
    ax.grid(alpha=0.3)

    err_residuals = np.sqrt(hist_cpp + hist_py)
    residuals = hist_cpp - hist_py
    with np.errstate(divide="ignore", invalid="ignore"):
        sigma_residuals = np.where(err_residuals > 0, residuals / err_residuals, 0)

    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    ax_res.axhline(0, color="gray", linestyle="--", alpha=0.5)
    ax_res.step(bin_centers, sigma_residuals, where="mid", color="black", linewidth=1.5)
    ax_res.set_xlabel("Value")
    ax_res.set_ylabel("Residuals [$\sigma$]")
    ax_res.grid(alpha=0.3)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return True


def _plot_displacement_split(
    cpp_root: Path,
    python_root: Path,
    output_dir: Path,
    plt: Any,
) -> list[str]:
    """Plot displacement distributions split by event-level single-strip presence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    axis_config = {
        "xz": {
            "branch": "displacement_p4_xz",
            "cluster_sizes": ["ClusterSize_Z1", "ClusterSize_Z2", "ClusterSize_Z3", "ClusterSize_Z4"],
        },
        "xy": {
            "branch": "displacement_p4_xy",
            "cluster_sizes": ["ClusterSize_Y1", "ClusterSize_Y2", "ClusterSize_Y3", "ClusterSize_Y4"],
        },
    }
    subset_config = [
        (True, "single_strip_events"),
        (False, "no_single_strip_events"),
    ]

    with uproot.open(cpp_root) as cpp_file, uproot.open(python_root) as py_file:
        cpp_trees = _find_ttrees(cpp_file)
        py_trees = _find_ttrees(py_file)

        if "AnalyzedData" not in cpp_trees or "AnalyzedData" not in py_trees:
            return generated

        cpp_tree = cpp_trees["AnalyzedData"]
        py_tree = py_trees["AnalyzedData"]

        for axis, config in axis_config.items():
            branch = config["branch"]
            cluster_size_branches = config["cluster_sizes"]
            required_branches = [branch, *cluster_size_branches]
            if any(name not in cpp_tree.keys() or name not in py_tree.keys() for name in required_branches):
                continue

            for include_single_strip, subset_name in subset_config:
                cpp_arr = _extract_displacement_subset(
                    cpp_tree,
                    displacement_branch=branch,
                    cluster_size_branches=cluster_size_branches,
                    include_single_strip=include_single_strip,
                )
                py_arr = _extract_displacement_subset(
                    py_tree,
                    displacement_branch=branch,
                    cluster_size_branches=cluster_size_branches,
                    include_single_strip=include_single_strip,
                )

                if cpp_arr.size == 0 and py_arr.size == 0:
                    continue

                title = (
                    f"AnalyzedData/{branch} - {subset_name}\n"
                    f"C++ entries={int(cpp_arr.size)}, Python entries={int(py_arr.size)}"
                )
                out_path = output_dir / f"AnalyzedData__{branch}__{subset_name}.png"
                if _plot_array_pair(cpp_arr, py_arr, title, out_path, plt):
                    generated.append(str(out_path))

    return generated


def _plot_significant_branches(
    cpp_root: Path,
    python_root: Path,
    rows: list[KSResult],
    output_dir: Path,
    max_plots: int,
    plt: Any,
) -> list[str]:
    if not rows or max_plots == 0:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_rows = rows[:max_plots] if max_plots > 0 else rows
    generated: list[str] = []

    with uproot.open(cpp_root) as cpp_file, uproot.open(python_root) as py_file:
        cpp_trees = _find_ttrees(cpp_file)
        py_trees = _find_ttrees(py_file)

        for row in selected_rows:
            if row.tree not in cpp_trees or row.tree not in py_trees:
                continue

            try:
                cpp_arr = _array_from_branch(cpp_trees[row.tree], row.branch)
                py_arr = _array_from_branch(py_trees[row.tree], row.branch)
            except Exception:  # noqa: BLE001
                continue

            if not (_is_numeric(cpp_arr) and _is_numeric(py_arr)):
                continue

            cpp_arr = _finite_only(cpp_arr.astype(np.float64, copy=False))
            py_arr = _finite_only(py_arr.astype(np.float64, copy=False))
            if cpp_arr.size == 0 or py_arr.size == 0:
                continue

            out_path = output_dir / _safe_plot_name(row.tree, row.branch)
            title = (
                f"{row.tree}/{row.branch}\n"
                f"KS={row.ks_statistic:.4f}, p={row.p_value:.3e}, "
                f"entries=({int(cpp_arr.size)},{int(py_arr.size)})"
            )
            if _plot_array_pair(cpp_arr, py_arr, title, out_path, plt):
                generated.append(str(out_path))

    return generated


def _plot_ks_pvalue_histograms(
    rows: list[KSResult],
    output_dir: Path,
    plt: Any,
) -> list[str]:
    if not rows:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    ks_values = np.asarray([row.ks_statistic for row in rows], dtype=np.float64)
    p_values = np.asarray([row.p_value for row in rows], dtype=np.float64)

    if ks_values.size > 0:
        fig_ks, ax_ks = plt.subplots(figsize=(7, 5), dpi=120)
        ax_ks.hist(ks_values, bins=40, histtype="stepfilled", alpha=0.7)
        ax_ks.set_xlabel("KS statistic")
        ax_ks.set_ylabel("Count")
        ax_ks.set_title("Distribution of KS statistics")
        ax_ks.grid(alpha=0.3)
        fig_ks.tight_layout()
        ks_path = output_dir / "ks_statistic_hist.png"
        fig_ks.savefig(ks_path)
        plt.close(fig_ks)
        generated.append(str(ks_path))

    if p_values.size > 0:
        fig_p, ax_p = plt.subplots(figsize=(7, 5), dpi=120)
        ax_p.hist(p_values, bins=np.linspace(0.0, 1.0, 41), histtype="stepfilled", alpha=0.7)
        ax_p.set_xlabel("p-value")
        ax_p.set_ylabel("Count")
        ax_p.set_title("Distribution of p-values")
        ax_p.grid(alpha=0.3)
        fig_p.tight_layout()
        p_path = output_dir / "p_value_hist.png"
        fig_p.savefig(p_path)
        plt.close(fig_p)
        generated.append(str(p_path))

    return generated


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare all numeric ROOT branches between two files with a two-sample KS test."
        )
    )
    parser.add_argument("cpp_root", type=Path, help="ROOT file from C++ reconstruction")
    parser.add_argument("python_root", type=Path, help="ROOT file from Python reconstruction")
    parser.add_argument(
        "--tree",
        action="append",
        default=None,
        help="Limit the comparison to one or more tree paths (repeatable)",
    )
    parser.add_argument(
        "--max-values",
        type=int,
        default=0,
        help="Optional cap per branch after flattening (0 means no cap)",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold for flagging different distributions",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used only when --max-values > 0",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=None,
        help=(
            "Prefix for generated reports (without extension). "
            "Defaults to 'compare_run<run>' in the current working directory."
        ),
    )
    parser.add_argument(
        "--plot-significant",
        action="store_true",
        help="Generate histogram overlays for statistically significant branches.",
    )
    parser.add_argument(
        "--plot-good",
        action="store_true",
        help="Generate histogram overlays for non-significant branches (p >= alpha).",
    )
    parser.add_argument(
        "--plot-max",
        type=int,
        default=30,
        help="Maximum number of significant branches to plot (0 disables plotting).",
    )
    parser.add_argument(
        "--plot-good-max",
        type=int,
        default=20,
        help="Maximum number of non-significant branches to plot (0 disables plotting).",
    )
    parser.add_argument(
        "--plot-sample-cap",
        type=int,
        default=50000,
        help="Optional cap of values per branch when making plots (0 means no cap).",
    )
    parser.add_argument(
        "--impact-report",
        action="store_true",
        help="Generate a practical PASS/WARN/ALERT impact report from KS results.",
    )
    parser.add_argument(
        "--plot-trigger"   ,
        action="store_true",
        help= "Plot trigger branches with a special style to help identify ordering/indexing issues.",
    )
    parser.add_argument(
        "--plot-ks-pvalues",
        action="store_true",
        help="Generate summary histograms for KS statistics and p-values.",
    )
    parser.add_argument(
        "--plot-branch",
        action="append",
        default=None,
        help=(
            "Plot only branches matching this wildcard pattern (repeatable), "
            "e.g. '*StripsID*' or 'Trigger*'."
        ),
    )
    parser.add_argument(
        "--plot-branch-max",
        type=int,
        default=50,
        help="Maximum number of pattern-matched branches to plot (0 disables).",
    )
    parser.add_argument(
        "--plot-displacement-single-strip-split",
        action="store_true",
        help=(
            "Generate separate displacement_p4_xz/xy plots for events that contain at least "
            "one single-strip cluster in the relevant view and for the remaining events."
        ),
    )
    return parser


def main() -> int:
    args = _make_parser().parse_args()
    user_provided_output_prefix = args.output_prefix is not None

    if args.output_prefix is None:
        cpp_stem = Path(args.cpp_root).stem
        py_stem = Path(args.python_root).stem
        run = py_stem.split("_")[2]
        args.output_prefix = Path.cwd() / f"compare_run{run}"

    global np
    global uproot
    global ak
    global scipy_ks_2samp

    import importlib

    try:

        np_module = importlib.import_module("numpy")
        uproot_module = importlib.import_module("uproot")
        ak_module = importlib.import_module("awkward")
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "unknown")
        raise RuntimeError(
            "Missing required package '"
            f"{missing}' for ROOT comparison. Install: numpy uproot awkward"
        ) from exc

    np = np_module
    uproot = uproot_module
    ak = ak_module

    try:
        scipy_stats = importlib.import_module("scipy.stats")
        scipy_ks_2samp_module = scipy_stats.ks_2samp
    except ModuleNotFoundError:
        scipy_ks_2samp_module = None
    scipy_ks_2samp = scipy_ks_2samp_module

    if not args.cpp_root.exists():
        raise FileNotFoundError(f"C++ ROOT file not found: {args.cpp_root}")
    if not args.python_root.exists():
        raise FileNotFoundError(f"Python ROOT file not found: {args.python_root}")

    rng = np.random.default_rng(args.seed)

    results: list[KSResult] = []
    skipped: list[dict[str, str]] = []
    tree_inventory: dict[str, Any] = {
        "common": [],
        "only_cpp": [],
        "only_python": [],
        "n_common": 0,
        "n_only_cpp": 0,
        "n_only_python": 0,
    }
    branch_inventory: dict[str, Any] = {}

    with uproot.open(args.cpp_root) as cpp_file, uproot.open(args.python_root) as py_file:
        cpp_trees = _find_ttrees(cpp_file)
        py_trees = _find_ttrees(py_file)

        common_trees = sorted(set(cpp_trees) & set(py_trees))
        cpp_only_trees = sorted(set(cpp_trees) - set(py_trees))
        py_only_trees = sorted(set(py_trees) - set(cpp_trees))

        tree_inventory = {
            "common": common_trees.copy(),
            "only_cpp": cpp_only_trees,
            "only_python": py_only_trees,
            "n_common": len(common_trees),
            "n_only_cpp": len(cpp_only_trees),
            "n_only_python": len(py_only_trees),
        }

        if args.tree:
            selected = set(args.tree)
            common_trees = [tree for tree in common_trees if tree in selected]

        for tree_name in common_trees:
            cpp_tree = cpp_trees[tree_name]
            py_tree = py_trees[tree_name]

            cpp_branches = set(cpp_tree.keys())
            py_branches = set(py_tree.keys())

            common_branches = sorted(cpp_branches & py_branches)
            cpp_only = sorted(cpp_branches - py_branches)
            py_only = sorted(py_branches - cpp_branches)

            branch_inventory[tree_name] = {
                "common": common_branches,
                "only_cpp": cpp_only,
                "only_python": py_only,
                "n_common": len(common_branches),
                "n_only_cpp": len(cpp_only),
                "n_only_python": len(py_only),
            }

            for branch in cpp_only:
                skipped.append({
                    "tree": tree_name,
                    "branch": branch,
                    "reason": "branch only in C++ ROOT",
                })
            for branch in py_only:
                skipped.append({
                    "tree": tree_name,
                    "branch": branch,
                    "reason": "branch only in Python ROOT",
                })

            for branch in common_branches:
                try:
                    cpp_arr = _array_from_branch(cpp_tree, branch)
                    py_arr = _array_from_branch(py_tree, branch)
                except Exception as exc:  # noqa: BLE001
                    skipped.append({
                        "tree": tree_name,
                        "branch": branch,
                        "reason": f"read error: {exc}",
                    })
                    continue

                if not (_is_numeric(cpp_arr) and _is_numeric(py_arr)):
                    skipped.append({
                        "tree": tree_name,
                        "branch": branch,
                        "reason": "non-numeric branch",
                    })
                    continue

                cpp_arr = _finite_only(cpp_arr.astype(np.float64, copy=False))
                py_arr = _finite_only(py_arr.astype(np.float64, copy=False))

                if cpp_arr.size == 0 or py_arr.size == 0:
                    skipped.append({
                        "tree": tree_name,
                        "branch": branch,
                        "reason": "empty after finite filtering",
                    })
                    continue

                if args.max_values > 0:
                    if cpp_arr.size > args.max_values:
                        cpp_idx = rng.choice(cpp_arr.size, size=args.max_values, replace=False)
                        cpp_arr = cpp_arr[cpp_idx]
                    if py_arr.size > args.max_values:
                        py_idx = rng.choice(py_arr.size, size=args.max_values, replace=False)
                        py_arr = py_arr[py_idx]

                d_stat, p_value = _ks_2samp(cpp_arr, py_arr)
                cpp_mean, cpp_std, cpp_median = _summarize(cpp_arr)
                py_mean, py_std, py_median = _summarize(py_arr)

                results.append(
                    KSResult(
                        tree=tree_name,
                        branch=branch,
                        n_cpp=int(cpp_arr.size),
                        n_python=int(py_arr.size),
                        ks_statistic=d_stat,
                        p_value=p_value,
                        cpp_mean=cpp_mean,
                        py_mean=py_mean,
                        cpp_std=cpp_std,
                        py_std=py_std,
                        cpp_median=cpp_median,
                        py_median=py_median,
                        abs_mean_diff=abs(cpp_mean - py_mean),
                        ks_effect_label=_ks_effect_label(d_stat),
                        significant=(p_value < args.alpha),
                        note="",
                    )
                )

    results_sorted = sorted(results, key=lambda row: row.p_value)

    skip_reason_counts: dict[str, int] = {}
    for entry in skipped:
        reason = entry.get("reason", "unknown")
        skip_reason_counts[reason] = skip_reason_counts.get(reason, 0) + 1

    summary = {
        "cpp_root": str(args.cpp_root),
        "python_root": str(args.python_root),
        "tree_inventory": tree_inventory,
        "branch_inventory": branch_inventory,
        "n_compared_branches": len(results_sorted),
        "n_significant_at_alpha": int(sum(r.significant for r in results_sorted)),
        "alpha": args.alpha,
        "skip_reason_counts": skip_reason_counts,
        "top_10_smallest_p_value": [asdict(r) for r in results_sorted[:10]],
        "all_results": [asdict(r) for r in results_sorted],
        "skipped": skipped,
    }

    if user_provided_output_prefix:
        # If user passes --output-prefix, write reports under <prefix>/report/.
        report_dir = args.output_prefix / "report"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_stem = args.output_prefix.name if args.output_prefix.name else "compare_report"
        json_path = report_dir / f"{report_stem}.json"
        csv_path = report_dir / f"{report_stem}.csv"
        branches_path = report_dir / f"{report_stem}_branches.json"
        plots_dir = args.output_prefix / "plots"
    else:
        json_path = args.output_prefix.with_suffix(".json")
        csv_path = args.output_prefix.with_suffix(".csv")
        branches_path = Path(str(args.output_prefix) + "_branches.json")
        plots_dir = Path(str(args.output_prefix) + "_plots")

    generated_sig_plots: list[str] = []
    generated_good_plots: list[str] = []
    generated_trigger_plots: list[str] = []
    generated_summary_plots: list[str] = []
    generated_selected_plots: list[str] = []
    generated_displacement_split_plots: list[str] = []
    plot_note = "disabled"
    plot_sig_enabled = bool(args.plot_significant and args.plot_max != 0)
    plot_good_enabled = bool(args.plot_good and args.plot_good_max != 0)
    plot_trigger_enabled = bool(args.plot_trigger and args.plot_max != 0)
    plot_summary_enabled = bool(args.plot_ks_pvalues)
    plot_selected_enabled = bool(args.plot_branch and args.plot_branch_max != 0)
    plot_displacement_split_enabled = bool(args.plot_displacement_single_strip_split)
    if (
        plot_sig_enabled
        or plot_good_enabled
        or plot_trigger_enabled
        or plot_summary_enabled
        or plot_selected_enabled
        or plot_displacement_split_enabled
    ):
        significant_rows = [row for row in results_sorted if row.significant]
        good_rows = [row for row in results_sorted if not row.significant]
        trigger_rows = [row for row in results_sorted if "trigger" in row.branch.lower()]
        selected_rows = [
            row
            for row in results_sorted
            if plot_selected_enabled and _branch_matches_any_pattern(row.branch, args.plot_branch)
        ]
        try:
            matplotlib = importlib.import_module("matplotlib")
            matplotlib.use("Agg")
            plt = importlib.import_module("matplotlib.pyplot")
            if plot_sig_enabled:
                generated_sig_plots = _plot_significant_branches(
                    cpp_root=args.cpp_root,
                    python_root=args.python_root,
                    rows=significant_rows,
                    output_dir=plots_dir / "significant",
                    max_plots=args.plot_max,
                    #sample_cap=args.plot_sample_cap,
                    #rng=rng,
                    plt=plt,
                )
            if plot_good_enabled:
                generated_good_plots = _plot_significant_branches(
                    cpp_root=args.cpp_root,
                    python_root=args.python_root,
                    rows=good_rows,
                    output_dir=plots_dir / "good",
                    max_plots=args.plot_good_max,
                    #sample_cap=args.plot_sample_cap,
                    #rng=rng,
                    plt=plt,
                )
            if plot_trigger_enabled:
                generated_trigger_plots = _plot_significant_branches(
                    cpp_root=args.cpp_root,
                    python_root=args.python_root,
                    rows=trigger_rows,
                    output_dir=plots_dir / "triggers",
                    max_plots=100,
                    #sample_cap=args.plot_sample_cap,
                    #rng=rng,
                    plt=plt,
                )
            if plot_summary_enabled:
                generated_summary_plots = _plot_ks_pvalue_histograms(
                    rows=results_sorted,
                    output_dir=plots_dir / "summary",
                    plt=plt,
                )
            if plot_selected_enabled:
                generated_selected_plots = _plot_significant_branches(
                    cpp_root=args.cpp_root,
                    python_root=args.python_root,
                    rows=selected_rows,
                    output_dir=plots_dir / "selected",
                    max_plots=args.plot_branch_max,
                    plt=plt,
                )
            if plot_displacement_split_enabled:
                generated_displacement_split_plots = _plot_displacement_split(
                    cpp_root=args.cpp_root,
                    python_root=args.python_root,
                    output_dir=plots_dir / "displacement_split",
                    plt=plt,
                )
            plot_note = "ok"
        except ModuleNotFoundError:
            plot_note = "matplotlib not installed"

    summary["plots"] = {
        "enabled": bool(
            plot_sig_enabled
            or plot_good_enabled
            or plot_trigger_enabled
            or plot_summary_enabled
            or plot_selected_enabled
            or plot_displacement_split_enabled
        ),
        "status": plot_note,
        "directory": str(plots_dir),
        "significant": {
            "enabled": plot_sig_enabled,
            "max": args.plot_max,
            "n_generated": len(generated_sig_plots),
            "directory": str(plots_dir / "significant"),
            "files": generated_sig_plots,
        },
        "good": {
            "enabled": plot_good_enabled,
            "max": args.plot_good_max,
            "n_generated": len(generated_good_plots),
            "directory": str(plots_dir / "good"),
            "files": generated_good_plots,
        },
        "triggers": {
            "enabled": plot_trigger_enabled,
            "max": args.plot_max,
            "n_generated": len(generated_trigger_plots),
            "directory": str(plots_dir / "triggers"),
            "files": generated_trigger_plots,
        },
        "summary": {
            "enabled": plot_summary_enabled,
            "n_generated": len(generated_summary_plots),
            "directory": str(plots_dir / "summary"),
            "files": generated_summary_plots,
        },
        "selected": {
            "enabled": plot_selected_enabled,
            "patterns": args.plot_branch or [],
            "max": args.plot_branch_max,
            "n_generated": len(generated_selected_plots),
            "directory": str(plots_dir / "selected"),
            "files": generated_selected_plots,
        },
        "displacement_split": {
            "enabled": plot_displacement_split_enabled,
            "n_generated": len(generated_displacement_split_plots),
            "directory": str(plots_dir / "displacement_split"),
            "files": generated_displacement_split_plots,
        },
        "n_generated": (
            len(generated_sig_plots)
            + len(generated_good_plots)
            + len(generated_trigger_plots)
            + len(generated_summary_plots)
            + len(generated_selected_plots)
            + len(generated_displacement_split_plots)
        ),
        "files": (
            generated_sig_plots
            + generated_good_plots
            + generated_trigger_plots
            + generated_summary_plots
            + generated_selected_plots
            + generated_displacement_split_plots
        ),
    }

    impact_report = None
    impact_path = Path(str(args.output_prefix) + "_impact.json")
    if args.impact_report:
        impact_report = _build_impact_report(results_sorted, args.alpha)
        summary["impact_report"] = impact_report

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    if impact_report is not None:
        with impact_path.open("w", encoding="utf-8") as handle:
            json.dump(impact_report, handle, indent=2)

    _write_csv(csv_path, results_sorted)

    # Write a compact branch-inventory file: common vs unique per tree.
    branches_doc: dict[str, Any] = {
        "cpp_root": str(args.cpp_root),
        "python_root": str(args.python_root),
        "tree_inventory": tree_inventory,
        "branch_inventory": branch_inventory,
        "skip_reason_counts": skip_reason_counts,
    }
    with branches_path.open("w", encoding="utf-8") as handle:
        json.dump(branches_doc, handle, indent=2)

    print(f"Compared numeric branches: {len(results_sorted)}")
    print(f"Significant differences (p < {args.alpha}): {summary['n_significant_at_alpha']}")
    print(f"Skipped branches: {len(skipped)}")
    print(f"  Skip reasons: {skip_reason_counts}")
    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")
    print(f"Branch inventory: {branches_path}")
    if impact_report is not None:
        print(
            f"Impact report: {impact_path} "
            f"({impact_report['impact_level']}: {impact_report['interpretation']})"
        )
    if summary["plots"]["enabled"]:
        print(
            f"Plots: {summary['plots']['n_generated']} generated in "
            f"{summary['plots']['directory']} ({summary['plots']['status']})"
        )
        print(
            f"  Significant: {summary['plots']['significant']['n_generated']} "
            f"in {summary['plots']['significant']['directory']}"
        )
        print(
            f"  Good: {summary['plots']['good']['n_generated']} "
            f"in {summary['plots']['good']['directory']}"
        )
        print(
            f"  Summary: {summary['plots']['summary']['n_generated']} "
            f"in {summary['plots']['summary']['directory']}"
        )
        print(
            f"  Selected: {summary['plots']['selected']['n_generated']} "
            f"in {summary['plots']['selected']['directory']}"
        )
        print(
            f"  Displacement split: {summary['plots']['displacement_split']['n_generated']} "
            f"in {summary['plots']['displacement_split']['directory']}"
        )

    if results_sorted:
        print("Most different branches by p-value:")
        for row in results_sorted[:10]:
            print(
                f"  {row.tree}/{row.branch}: p={row.p_value:.3e}, "
                f"KS={row.ks_statistic:.4f}, n=({row.n_cpp},{row.n_python})"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
