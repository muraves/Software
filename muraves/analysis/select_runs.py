"""
Select the list of good runs for a given hodoscope, applying the agreed quality criteria.

Criteria (in the order they are applied):

  1. Raw run must exist            -> 'missing_run == False'  ("subruns" is an empty list
                                      when the raw files were not found)
  2. All sub-runs present          -> number of subruns == N_SUBRUNS_REQUIRED
                                      (NOT AVAILABLE in the current pkl files, see note below)
  3. Parsing succeeded             -> 'is_run_ok == True'     ("status": "ok")
  4. Missing/shifted bit frequency -> mismatch test passed AND mismatch_prob < MISMATCH_PROB_MAX
                                      (same definition as dev/good_runs/good_runs_stat.py)
  5. Pedestal quality              -> number of affected channels <= MAX_AFFECTED_CHANNELS
                                      (from pedestal_deviation_check/<COLOR>/*_SUMMARY.txt)

NOTE on criterion 2: 'read_summary_file' in muraves_lib.run_manager only exposes
'missing_run' (len(subruns) == 0), not the actual number of subruns, so the pkl files in
parsing_overview/ do not carry that information. The cut is implemented but is skipped with
a warning unless the dataframe has a subrun-count column (see N_SUBRUNS_COLUMNS). To enable
it: add the subrun count to RunValidation/read_summary_file and regenerate the pkl files.

Inputs:
  - parsing_overview/<COLOR>/results_<COLOR>_<version>.pkl        (built with read_summary_file)
  - pedestal_deviation_check/<COLOR>/<COLOR>_HISTchi2_outliers_SUMMARY.txt

Output:
  - <COLOR>_type<TYPE>_SELECTED_RUNS.txt    : one run number per line
  - <COLOR>_type<TYPE>_SELECTION_CUTFLOW.pdf: pie chart of the cut flow (--no-plot to skip)
  - optional csv with the per-run quantities used for the selection (--details)

Usage:
  python select_runs.py                          # all hodoscopes, type ADC
  python select_runs.py --hodoscope BLU --type BOTH --details
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display inside the container
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------- configuration

ANALYSIS_DIR = Path(__file__).resolve().parent
PARSING_OVERVIEW_DIR = ANALYSIS_DIR / "parsing_overview"
PEDESTAL_DIR = ANALYSIS_DIR / "pedestal_deviation_check"

HODOSCOPES = ["BLU", "NERO", "ROSSO"]
TYPES = ["ADC", "PIEDISTALLI", "BOTH"]

# Quality thresholds
N_SUBRUNS_REQUIRED = 4      # criterion 2, may change in the future
MISMATCH_PROB_MAX = 0.05    # criterion 4, probability that a line contains a corrupted value
MAX_AFFECTED_CHANNELS = 10  # criterion 5, pedestal outlier channels per run

# Number of events per file used to normalise the mismatch probability
# (same numbers as dev/good_runs/good_runs_stat.py)
N_EVENTS_PER_TYPE = {"ADC": 40000, "PIEDISTALLI": 50000}
N_LINES_PER_EVENT = 16
N_BITS_PER_LINE = 625

# Possible names of the subrun-count column (criterion 2), if it ever gets added
N_SUBRUNS_COLUMNS = ["n_subruns", "n_subrun", "subruns_counter", "number_of_subruns"]


# ---------------------------------------------------------------- loading

def load_parsing_overview(hodoscope, version="v0", parsing_overview_dir=PARSING_OVERVIEW_DIR):
    """Load the summary-file dataframe produced with run_manager.read_summary_file."""
    pkl_path = Path(parsing_overview_dir) / hodoscope / f"results_{hodoscope}_{version}.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(f"Parsing overview not found: {pkl_path}")
    df = pd.read_pickle(pkl_path)
    print(f"[{hodoscope}] loaded {len(df)} summary entries from {pkl_path.name}")
    return df


def load_pedestal_outliers(hodoscope, pedestal_dir=PEDESTAL_DIR):
    """
    Read <COLOR>_HISTchi2_outliers_SUMMARY.txt and return a Series
    (index = run, value = number of affected channels).

    The file starts with a few '#' comment lines and then holds one
    "<run> <number_of_affected_channels>" pair per line.
    """
    txt_path = Path(pedestal_dir) / hodoscope / f"{hodoscope}_HISTchi2_outliers_SUMMARY.txt"
    if not txt_path.exists():
        print(f"[{hodoscope}] [WARNING] pedestal summary not found: {txt_path}")
        return None

    runs, n_channels = [], []
    with open(txt_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != 2:
                print(f"[{hodoscope}] [WARNING] skipping malformed pedestal line: {line!r}")
                continue
            try:
                runs.append(int(fields[0]))
                n_channels.append(int(fields[1]))
            except ValueError:
                print(f"[{hodoscope}] [WARNING] skipping malformed pedestal line: {line!r}")

    outliers = pd.Series(n_channels, index=pd.Index(runs, name="run"),
                         name="n_affected_channels")
    outliers = outliers[~outliers.index.duplicated(keep="last")]
    print(f"[{hodoscope}] loaded pedestal info for {len(outliers)} runs from {txt_path.name}")
    return outliers


# ---------------------------------------------------------------- quality flags

def add_quality_flags(df):
    """Add the derived quantities used by the selection to the summary dataframe."""
    df = df.copy()

    # Probability that a line contains at least one corrupted value.
    # 'mismatch_counter' is NaN when the summary file reports no mismatch at all,
    # which means zero mismatches, not "unknown".
    counter = pd.to_numeric(df["mismatch_counter"], errors="coerce")
    no_mismatch = df["has_mismatches"].ne(True)
    counter = counter.mask(counter.isna() & no_mismatch, 0.0)

    n_events = df["type"].map(N_EVENTS_PER_TYPE)
    df["mismatch_prob"] = (
        counter * N_BITS_PER_LINE / (n_events * N_LINES_PER_EVENT)
    )

    # A run passes the mismatch test if it has no mismatches at all, or if all of
    # its mismatches are recoverable.
    df["mismatch_test_passed"] = (
        df["has_mismatches"].eq(False)
        | (df["has_mismatches"].eq(True) & df["has_unrecoverable_mismatches"].eq(False))
    )
    return df


def find_n_subruns_column(df):
    """Return the name of the subrun-count column, or None if the pkl does not carry it."""
    for column in N_SUBRUNS_COLUMNS:
        if column in df.columns:
            return column
    return None


# ---------------------------------------------------------------- selection

def select_runs(df, pedestal_outliers, run_type="ADC",
                n_subruns_required=N_SUBRUNS_REQUIRED,
                mismatch_prob_max=MISMATCH_PROB_MAX,
                max_affected_channels=MAX_AFFECTED_CHANNELS,
                require_pedestal_info=False,
                label=""):
    """
    Apply the quality criteria and return (good_runs, details, cutflow).

    'good_runs' is a sorted numpy array of run numbers.
    'details'   is the per-run dataframe of the quantities used for the selection.
    'cutflow'   is the dataframe of the cut flow (runs left / removed at each step),
                used to draw the summary pie chart.

    run_type: 'ADC' or 'PIEDISTALLI' selects that file type only.
              'BOTH' requires the run to pass the criteria for both file types.

    require_pedestal_info: if True, runs missing from the pedestal summary are rejected;
                           if False (default) they are kept, and only counted.
    """
    assert run_type in TYPES, f"Unexpected type: {run_type}. Expected one of {TYPES}."

    df = add_quality_flags(df)
    if run_type != "BOTH":
        df = df[df["type"] == run_type]
    total_runs = df["run"].nunique()
    print(f"{label} starting from {total_runs} runs (type: {run_type})")

    # ---- criteria applied on the summary files (one row per run and file type)
    # Each entry is (label, condition to PASS the cut). The labels name the reason a run
    # is rejected, because that is what the cut flow and the pie chart report.
    cuts = [
        ("1. run N/A", df["missing_run"].eq(False)),
    ]

    n_subruns_column = find_n_subruns_column(df)
    if n_subruns_column is not None:
        cuts.append((
            f"2. not {n_subruns_required} subruns",
            df[n_subruns_column].eq(n_subruns_required),
        ))
    else:
        print(f"{label} [WARNING] no subrun-count column in the dataframe "
              f"(looked for {N_SUBRUNS_COLUMNS}): criterion 2 "
              f"('exactly {n_subruns_required} subruns') is SKIPPED. "
              f"read_summary_file only stores 'missing_run' (len(subruns) == 0).")

    cuts += [
        ("3. parsing failed", df["is_run_ok"].eq(True)),
        ("4a. unrecoverable mismatches", df["mismatch_test_passed"].eq(True)),
        (f"4b. mismatch_prob >= {mismatch_prob_max}", df["mismatch_prob"].lt(mismatch_prob_max)),
    ]

    # Sequential cut flow. A run survives only if ALL of its selected rows survive:
    # for run_type 'BOTH' this means both the ADC and the PIEDISTALLI file must pass.
    # All percentages are relative to the initial number of runs, so that the
    # "removed" column can be summed across the steps.
    print(f"{label} cut flow (percentages w.r.t. the {total_runs} initial runs):")
    cutflow = []
    mask = pd.Series(True, index=df.index)
    surviving = total_runs
    for name, cut in cuts:
        mask &= cut.fillna(False).astype(bool)
        previous, surviving = surviving, _surviving_runs(df, mask, run_type).size
        cutflow.append({"cut": name, "runs_left": surviving, "removed": previous - surviving})
        print(_cutflow_line(label, name, surviving, previous - surviving, total_runs))

    good_runs = _surviving_runs(df, mask, run_type)

    # ---- criterion 5: pedestal quality, one value per run (no file type)
    details = (
        df[df["run"].isin(good_runs)]
        .groupby("run")
        .agg(mismatch_prob=("mismatch_prob", "max"),
             mismatch_counter=("mismatch_counter", "max"))
        .reset_index()
    )

    if pedestal_outliers is None:
        print(f"{label} [WARNING] no pedestal summary available: criterion 5 is SKIPPED.")
        details["n_affected_channels"] = np.nan
    else:
        details["n_affected_channels"] = details["run"].map(pedestal_outliers)
        n_missing = int(details["n_affected_channels"].isna().sum())
        if n_missing:
            action = "rejected" if require_pedestal_info else "kept"
            print(f"{label} [INFO] {n_missing} runs are not in the pedestal summary: {action}.")

        pedestal_ok = details["n_affected_channels"].le(max_affected_channels)
        if not require_pedestal_info:
            pedestal_ok |= details["n_affected_channels"].isna()

        previous = len(details)
        details = details[pedestal_ok]
        good_runs = np.sort(details["run"].to_numpy())
        cutflow.append({"cut": "5. bad pedestal", "runs_left": len(good_runs),
                        "removed": previous - len(good_runs)})
        print(_cutflow_line(label, "5. bad pedestal", len(good_runs),
                            previous - len(good_runs), total_runs))

    fraction = len(good_runs) / total_runs * 100 if total_runs else 0.0
    print(f"{label} SELECTED {len(good_runs)} runs out of {total_runs} ({fraction:.2f}%)")

    cutflow = pd.DataFrame(cutflow)
    cutflow["total_runs"] = total_runs
    cutflow["removed_percent"] = cutflow["removed"] / total_runs * 100 if total_runs else np.nan
    cutflow["runs_left_percent"] = cutflow["runs_left"] / total_runs * 100 if total_runs else np.nan
    return good_runs, details.reset_index(drop=True), cutflow


def plot_cutflow_pie(cutflow, output_path, hodoscope="", run_type=""):
    """
    Pie chart of the selection: one slice per cut (the runs it removes) plus one
    slice for the selected runs. All slices are fractions of the initial number of
    runs, so they add up to 100%.

    Cuts that remove nothing get no slice (they would be invisible); they are
    listed under the chart instead.
    """
    total_runs = int(cutflow["total_runs"].iloc[0])
    selected = int(cutflow["runs_left"].iloc[-1])

    removing = cutflow[cutflow["removed"] > 0]
    empty_cuts = cutflow.loc[cutflow["removed"] == 0, "cut"].tolist()

    labels = list(removing["cut"]) + ["SELECTED"]
    sizes = list(removing["removed"]) + [selected]

    # Greys/reds for the rejected runs, green for the selected ones
    rejected_colors = plt.cm.Reds(np.linspace(0.35, 0.8, len(removing)))
    colors = list(rejected_colors) + ["#2ca02c"]
    explode = [0.0] * len(removing) + [0.05]

    def autopct(percent):
        return f"{percent:.2f}%\n({int(round(percent * total_runs / 100))})"

    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, _, autotexts = ax.pie(
        sizes,
        colors=colors,
        explode=explode,
        startangle=90,
        counterclock=False,
        autopct=autopct,
        pctdistance=0.75,
        textprops={"fontsize": 9},
        wedgeprops={"edgecolor": "white", "linewidth": 1},
    )
    # Thin slices have no room for a label inside: move those outside, with a leader line
    # and a staggered radius so that consecutive small slices do not overlap.
    n_outside = 0
    for wedge, autotext, size in zip(wedges, autotexts, sizes):
        autotext.set_fontweight("bold")
        if size / sum(sizes) >= 0.06:
            autotext.set_color("white")
            continue
        angle = np.deg2rad(0.5 * (wedge.theta1 + wedge.theta2))
        x, y = np.cos(angle), np.sin(angle)
        radius = 1.25 + 0.22 * (n_outside % 2)
        n_outside += 1
        autotext.set_position((radius * x, radius * y))
        autotext.set_color("black")
        autotext.set_horizontalalignment("left" if x >= 0 else "right")
        ax.plot([1.02 * x, (radius - 0.04) * x], [1.02 * y, (radius - 0.04) * y],
                color="grey", linewidth=0.8, clip_on=False)

    ax.legend(wedges, [f"{name}  ({size} runs)" for name, size in zip(labels, sizes)],
              title="Removed by / selected", loc="center left",
              bbox_to_anchor=(1.0, 0.5), fontsize=9)
    ax.set_title(f"{hodoscope} - type {run_type}\nRun selection: "
                 f"{selected} good runs out of {total_runs} "
                 f"({selected / total_runs * 100:.2f}%)")
    ax.axis("equal")

    footnote = ("Slices are fractions of the initial number of runs. Cuts are applied in "
                "sequence, so each slice\nis what that cut removes on top of the previous ones.")
    if empty_cuts:
        footnote += "\nCuts that removed no additional run: " + ", ".join(empty_cuts) + "."
    fig.text(0.02, 0.02, footnote, fontsize=8, style="italic", va="bottom")

    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(output_path, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return output_path


def _cutflow_line(label, name, surviving, removed, total_runs):
    """Format one line of the cut flow, with percentages w.r.t. the initial number of runs."""
    def percentage(n):
        return f"{n / total_runs * 100:6.2f}%" if total_runs else "   n/a"

    return (f"{label}   {name:<32} {surviving:>7} runs left ({percentage(surviving)}) "
            f"| removed {removed:>6} ({percentage(removed)})")


def _surviving_runs(df, mask, run_type):
    """
    Run numbers whose rows all pass 'mask'. For run_type 'BOTH' the run must also
    have both file types present in the dataframe.
    """
    passed = df.assign(passed=mask).groupby("run")["passed"].all()
    runs = passed[passed].index

    if run_type == "BOTH":
        both_types = df.groupby("run")["type"].nunique().ge(len(N_EVENTS_PER_TYPE))
        runs = runs.intersection(both_types[both_types].index)

    return np.sort(runs.to_numpy())


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hodoscope", default="ALL", choices=HODOSCOPES + ["ALL"],
                        help="hodoscope colour to process (default: ALL)")
    parser.add_argument("--type", dest="run_type", default="ADC", choices=TYPES,
                        help="file type the criteria are applied to (default: ADC)")
    parser.add_argument("--version", default="v0", help="parsing version (default: v0)")
    parser.add_argument("--mismatch-prob-max", type=float, default=MISMATCH_PROB_MAX,
                        help=f"maximum mismatch probability (default: {MISMATCH_PROB_MAX})")
    parser.add_argument("--max-affected-channels", type=int, default=MAX_AFFECTED_CHANNELS,
                        help="maximum number of pedestal outlier channels "
                             f"(default: {MAX_AFFECTED_CHANNELS})")
    parser.add_argument("--n-subruns", type=int, default=N_SUBRUNS_REQUIRED,
                        help=f"required number of subruns (default: {N_SUBRUNS_REQUIRED})")
    parser.add_argument("--require-pedestal-info", action="store_true",
                        help="reject runs that are not listed in the pedestal summary "
                             "(default: keep them)")
    parser.add_argument("--details", action="store_true",
                        help="also write a csv with the quantities used for the selection")
    parser.add_argument("--no-plot", action="store_true",
                        help="do not save the cut flow pie chart")
    parser.add_argument("--output-dir", default=str(ANALYSIS_DIR),
                        help="where to write the run lists (default: this directory)")
    args = parser.parse_args()

    hodoscopes = HODOSCOPES if args.hodoscope == "ALL" else [args.hodoscope]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for hodoscope in hodoscopes:
        label = f"[{hodoscope}]"
        print(f"\n{'=' * 70}\n{hodoscope}\n{'=' * 70}")

        df = load_parsing_overview(hodoscope, version=args.version)
        pedestal_outliers = load_pedestal_outliers(hodoscope)

        good_runs, details, cutflow = select_runs(
            df,
            pedestal_outliers,
            run_type=args.run_type,
            n_subruns_required=args.n_subruns,
            mismatch_prob_max=args.mismatch_prob_max,
            max_affected_channels=args.max_affected_channels,
            require_pedestal_info=args.require_pedestal_info,
            label=label,
        )

        output_path = output_dir / f"{hodoscope}_type{args.run_type}_SELECTED_RUNS.txt"
        with open(output_path, "w") as f:
            f.writelines(f"{run}\n" for run in good_runs)
        print(f"{label} run list written to {output_path}")

        if args.details:
            details_path = output_dir / f"{hodoscope}_type{args.run_type}_SELECTED_RUNS.csv"
            details.to_csv(details_path, index=False)
            print(f"{label} details written to {details_path}")

        if not args.no_plot:
            plot_path = output_dir / f"{hodoscope}_type{args.run_type}_SELECTION_CUTFLOW.pdf"
            plot_cutflow_pie(cutflow, plot_path, hodoscope=hodoscope, run_type=args.run_type)
            print(f"{label} cut flow pie chart written to {plot_path}")


if __name__ == "__main__":
    main()
