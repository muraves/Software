import uproot
import pandas as pd
import argparse
import re
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

DEFAULT_RUN_DIR = "/user/abiolchi/muraves_outputs/RECONSTRUCTED/NERO/v0"
DEFAULT_RUN_PATTERN = "MURAVES_AnalyzedData_run{run}.root"
DEFAULT_ROOT_FILE = f"{DEFAULT_RUN_DIR}/{DEFAULT_RUN_PATTERN.format(run=2500)}"

# Scalar branches available in the AnalyzedData tree.
# Key = branch name in ROOT file, Value = human-readable label for plots.
FEATURES_LABEL = {
    # --- Cluster counts per plane ---
    "Nclusters_Y1": "N clusters Y1",
    "Nclusters_Y2": "N clusters Y2",
    "Nclusters_Y3": "N clusters Y3",
    
    "Nclusters_Z1": "N clusters Z1",
    "Nclusters_Z2": "N clusters Z2",
    "Nclusters_Z3": "N clusters Z3",
    
    # --- Cluster size per plane (n entries in per-cluster array) ---
    #"nClusterSize_Y1": "Cluster size Y1",
    #"nClusterSize_Y2": "Cluster size Y2",
    #"nClusterSize_Y3": "Cluster size Y3",
    #"nClusterSize_Y4": "Cluster size Y4",
    #"nClusterSize_Z1": "Cluster size Z1",
    #"nClusterSize_Z2": "Cluster size Z2",
    #"nClusterSize_Z3": "Cluster size Z3",
    #"nClusterSize_Z4": "Cluster size Z4",
    # --- N strips fired per plane ---
    "nStripsPosition_Y1": "N strips Y1",
    "nStripsPosition_Y2": "N strips Y2",
    "nStripsPosition_Y3": "N strips Y3",
    
    "nStripsPosition_Z1": "N strips Z1",
    "nStripsPosition_Z2": "N strips Z2",
    "nStripsPosition_Z3": "N strips Z3",
    
    # --- N strips with energy deposit per plane ---
    #"nStripsEnergy_Y1": "N strips energy Y1",
    #"nStripsEnergy_Y2": "N strips energy Y2",
    #"nStripsEnergy_Y3": "N strips energy Y3",
    #"nStripsEnergy_Y4": "N strips energy Y4",
    #"nStripsEnergy_Z1": "N strips energy Z1",
    #"nStripsEnergy_Z2": "N strips energy Z2",
    #"nStripsEnergy_Z3": "N strips energy Z3",
    #"nStripsEnergy_Z4": "N strips energy Z4",
    ## --- N strip IDs per plane ---
    #"nStripsID_Y1": "N strip IDs Y1",
    #"nStripsID_Y2": "N strip IDs Y2",
    #"nStripsID_Y3": "N strip IDs Y3",
    #"nStripsID_Y4": "N strip IDs Y4",
    #"nStripsID_Z1": "N strip IDs Z1",
    #"nStripsID_Z2": "N strip IDs Z2",
    #"nStripsID_Z3": "N strip IDs Z3",
    #"nStripsID_Z4": "N strip IDs Z4",
    # --- Track multiplicities ---
    "Ntracks_3p_xy": "N tracks 3p XY",
    "Ntracks_3p_xz": "N tracks 3p XZ",
    # --- Best-track chi-square (3-plane fit) ---
    "BestTrack_3p_ChiSquare_xy": "Best chi2 3p XY",
    "BestTrack_3p_ChiSquare_xz": "Best chi2 3p XZ",
    "BestChi_xy": "Best chi2 XY",
    "BestChi_xz": "Best chi2 XZ",
    # --- Best-track chi-square (4-plane fit) ---
    #"BestTrack_4p_ChiSquare_xy": "Best chi2 4p XY",
    #"BestTrack_4p_ChiSquare_xz": "Best chi2 4p XZ",
    # --- Best-track energy ---
    "BestEnergy_xy": "Best energy XY",
    "BestEnergy_xz": "Best energy XZ",
    # --- Scattering angles ---
    "BestTracks_ScatteringAngle_xy": "Scattering angle XY",
    "BestTracks_ScatteringAngle_xz": "Scattering angle XZ",
    # --- Track direction angles ---
    "Theta_3p": "Theta 3p",
    "Theta_4p": "Theta 4p",
    "Phi_3p":   "Phi 3p",
    "Phi_4p":   "Phi 4p",
    # --- Detector / run conditions ---
    #"Temperature": "Temperature",
    #"TriggerRate": "Trigger rate",
    #"WorkingPoint": "Working point",
    "nTriggerMaskChannels": "N trigger mask ch.",
    "nTriggerMaskStrips":   "N trigger mask strips",
    #"nTriggerMaskSize":     "N trigger mask size",
    # --- Aggregated vector features (computed by compute_vector_aggregations) ---
    # Mean cluster size per plane
    "mean_ClusterSize_Y1": "Mean cluster size Y1",
    "mean_ClusterSize_Y2": "Mean cluster size Y2",
    "mean_ClusterSize_Y3": "Mean cluster size Y3",
    "mean_ClusterSize_Z1": "Mean cluster size Z1",
    "mean_ClusterSize_Z2": "Mean cluster size Z2",
    "mean_ClusterSize_Z3": "Mean cluster size Z3",


    


    # Mean cluster energy per plane
    "mean_ClusterEnergy_Y1": "Mean cluster energy Y1",
    "mean_ClusterEnergy_Y2": "Mean cluster energy Y2",
    "mean_ClusterEnergy_Y3": "Mean cluster energy Y3",
    "mean_ClusterEnergy_Z1": "Mean cluster energy Z1",
    "mean_ClusterEnergy_Z2": "Mean cluster energy Z2",
    "mean_ClusterEnergy_Z3": "Mean cluster energy Z3",
    
    # Mean strip energy per plane
    "mean_StripsEnergy_Y1": "Mean strip energy Y1",
    "mean_StripsEnergy_Y2": "Mean strip energy Y2",
    "mean_StripsEnergy_Y3": "Mean strip energy Y3",
    "mean_StripsEnergy_Z1": "Mean strip energy Z1",
    "mean_StripsEnergy_Z2": "Mean strip energy Z2",
    "mean_StripsEnergy_Z3": "Mean strip energy Z3",
    
    # Max strip energy per plane
    "max_StripsEnergy_Y1": "Max strip energy Y1",
    "max_StripsEnergy_Y2": "Max strip energy Y2",
    "max_StripsEnergy_Y3": "Max strip energy Y3",
    "max_StripsEnergy_Z1": "Max strip energy Z1",
    "max_StripsEnergy_Z2": "Max strip energy Z2",
    "max_StripsEnergy_Z3": "Max strip energy Z3",
    
    # RMS of track residuals (fit quality)
    "rms_Residue_Track3p_z1": "RMS residue 3p Z1",
    "rms_Residue_Track3p_z2": "RMS residue 3p Z2",
    "rms_Residue_Track3p_z3": "RMS residue 3p Z3",
    "rms_Residue_Track3p_y1": "RMS residue 3p Y1",
    "rms_Residue_Track3p_y2": "RMS residue 3p Y2",
    "rms_Residue_Track3p_y3": "RMS residue 3p Y3",
    # Min chi-square across tracks
    "min_chiSquare_3p_xy": "Min chi2 3p XY",
    "min_chiSquare_3p_xz": "Min chi2 3p XZ",
    # Mean scattering angle across tracks
    "mean_ScatteringAngle_xy": "Mean scattering angle XY",
    "mean_ScatteringAngle_xz": "Mean scattering angle XZ",
    # Mean cluster position per plane
    "mean_ClusterPosition_Y1": "Mean cluster pos Y1",
    "mean_ClusterPosition_Y2": "Mean cluster pos Y2",
    "mean_ClusterPosition_Y3": "Mean cluster pos Y3",
    "mean_ClusterPosition_Z1": "Mean cluster pos Z1",
    "mean_ClusterPosition_Z2": "Mean cluster pos Z2",
    "mean_ClusterPosition_Z3": "Mean cluster pos Z3",

    # Mean slope and intercept of 3p tracks
    "mean_Intercept_3p_xy": "Mean intercept 3p XY",
    "mean_Intercept_3p_xz": "Mean intercept 3p XZ",
    "mean_Slope_3p_xy":     "Mean slope 3p XY",
    "mean_Slope_3p_xz":     "Mean slope 3p XZ",
    # Mean track energy (3p)
    "mean_TrackEnergy_3p_xy": "Mean track energy 3p XY",
    "mean_TrackEnergy_3p_xz": "Mean track energy 3p XZ",


    ## ===4thplane info===
    #"Nclusters_Z4": "N clusters Z4",
    #"Nclusters_Y4": "N clusters Y4",
    #"nStripsPosition_Y4": "N strips Y4",
    #"nStripsPosition_Z4": "N strips Z4",
    ## Mean slope and intercept of 4p tracks
    #"mean_Intercept_4p_xy": "Mean intercept 4p XY",
    #"mean_Intercept_4p_xz": "Mean intercept 4p XZ",
    ## Mean expected position on 4th plane
    #"mean_ExpectedPosition_OnPlane4th_xy": "Mean exp. pos. plane4 XY",
    #"mean_ExpectedPosition_OnPlane4th_xz": "Mean exp. pos. plane4 XZ",
    ## The rest
    #"mean_Slope_4p_xy":     "Mean slope 4p XY",
    #"mean_Slope_4p_xz":     "Mean slope 4p XZ",
    #"mean_ClusterSize_Z4": "Mean cluster size Z4",
    #"mean_ClusterSize_Y4": "Mean cluster size Y4",
    #"mean_ClusterPosition_Y4": "Mean cluster pos Y4",
    #"mean_ClusterPosition_Z4": "Mean cluster pos Z4",
    #"mean_ClusterEnergy_Y4": "Mean cluster energy Y4",
    #"mean_ClusterEnergy_Z4": "Mean cluster energy Z4",
    #"mean_StripsEnergy_Y4": "Mean strip energy Y4",
    #"mean_StripsEnergy_Z4": "Mean strip energy Z4",
    #"max_StripsEnergy_Y4": "Max strip energy Y4",
    #"max_StripsEnergy_Z4": "Max strip energy Z4",
}


# ---------------------------------------------------------------------------
# Branches NOT used in PCA, available for post-clustering inspection.
# Scalars are plotted directly; vectors are mean-aggregated per event.
# ---------------------------------------------------------------------------
def build_unused_dataframe(
    df: pd.DataFrame,
    features_used: list,
    vector_agg_sources: set,
) -> tuple:
    """
    Build a DataFrame of branches NOT used in PCA, for post-clustering inspection.

    Rules:
    - Branches in `features_used` (PCA scalar features) are excluded.
    - Branches in `vector_agg_sources` (source of VECTOR_AGGREGATIONS) are excluded.
    - `n<Uppercase>` counter branches (e.g. nClusterSize_Y1) are excluded — they
      duplicate the information already in the scalar count features.
    - Scalar numeric branches are kept as-is.
    - Vector (per-event array) branches are mean-aggregated to one value per event.
    - Non-numeric branches (e.g. string columns) are skipped.

    Returns (unused_df, unused_labels) or (None, None) if nothing remains.
    """
    excluded = set(features_used) | vector_agg_sources
    parts = {}
    labels = {}

    for col in df.columns:
        if col in excluded:
            continue
        # Skip n<Uppercase> size-counter branches
        if re.match(r'^n[A-Z]', col):
            continue
        series = df[col]
        valid = series.dropna()
        if valid.empty:
            continue
        first = valid.iloc[0]
        if np.isscalar(first):
            if pd.api.types.is_numeric_dtype(series):
                parts[col] = series.values
                labels[col] = col.replace("_", " ")
        else:
            # Vector branch — mean-aggregate
            agg_col = f"mean_{col}"
            parts[agg_col] = series.apply(lambda v: _agg_series(v, "mean")).values
            labels[agg_col] = f"Mean {col.replace('_', ' ')}"

    if not parts:
        return None, None

    unused_df = pd.DataFrame(parts).reset_index(drop=True)
    return unused_df, labels


def load_root_to_dataframe(file_path: str) -> pd.DataFrame:
    """Load the first tree of a ROOT file into a pandas DataFrame."""
    with uproot.open(file_path) as f:
        tree = f[f.keys()[0]]
        df = tree.arrays(library="pd")
    return df


def load_multiple_root_files(file_paths: list) -> pd.DataFrame:
    """
    Load one or more ROOT files and concatenate into a single DataFrame.
    When multiple files are provided, a 'run' column (int) is added whose value
    is extracted from the filename pattern 'run<N>', or falls back to the list index.
    """
    multi = len(file_paths) > 1
    dfs = []
    for idx, path in enumerate(file_paths):
        print(f"  Loading: {path}")
        df_single = load_root_to_dataframe(path)
        if multi:
            m = re.search(r'run(\d+)', Path(path).stem)
            df_single["run"] = int(m.group(1)) if m else idx
            tag = f"  (run {df_single['run'].iloc[0]})"
        else:
            tag = ""
        dfs.append(df_single)
        print(f"    → {len(df_single)} events{tag}")
    result = pd.concat(dfs, ignore_index=True)
    if multi:
        print(f"Total events after concatenation: {len(result)}")
    return result


def is_scalar_series(series: pd.Series) -> bool:
    """Return True if every entry of the series is a scalar (not an array)."""
    non_null = series.dropna()
    if non_null.empty:
        return True
    return bool(np.isscalar(non_null.iloc[0]))


# ---------------------------------------------------------------------------
# Vector branch aggregations
# (branch_name, aggregation): new_column_name
# ---------------------------------------------------------------------------
VECTOR_AGGREGATIONS: dict[str, tuple[str, str]] = {
    # Mean cluster size per plane
    **{f"mean_ClusterSize_{p}{i}": (f"ClusterSize_{p}{i}", "mean")
       for p in ("Y", "Z") for i in range(1, 5)},
    # Mean cluster energy per plane
    **{f"mean_ClusterEnergy_{p}{i}": (f"ClusterEnergy_{p}{i}", "mean")
       for p in ("Y", "Z") for i in range(1, 5)},
    # Mean & max strip energy per plane
    **{f"mean_StripsEnergy_{p}{i}": (f"StripsEnergy_{p}{i}", "mean")
       for p in ("Y", "Z") for i in range(1, 5)},
    **{f"max_StripsEnergy_{p}{i}": (f"StripsEnergy_{p}{i}", "max")
       for p in ("Y", "Z") for i in range(1, 5)},
    # RMS of track residuals
    **{f"rms_Residue_Track3p_{p}{i}": (f"Residue_Track3p_{p}{i}", "rms")
       for p in ("z", "y") for i in range(1, 4)},
    # Min chi-square across tracks
    "min_chiSquare_3p_xy": ("chiSquare_3p_xy", "min"),
    "min_chiSquare_3p_xz": ("chiSquare_3p_xz", "min"),
    # Mean scattering angle across tracks
    "mean_ScatteringAngle_xy": ("ScatteringAngle_xy", "mean"),
    "mean_ScatteringAngle_xz": ("ScatteringAngle_xz", "mean"),
    # Mean cluster position per plane
    **{f"mean_ClusterPosition_{p}{i}": (f"ClusterPosition_{p}{i}", "mean")
       for p in ("Y", "Z") for i in range(1, 5)},
    # Mean slope and intercept of 3p tracks
    "mean_Intercept_3p_xy": ("Intercept_3p_xy", "mean"),
    "mean_Intercept_3p_xz": ("Intercept_3p_xz", "mean"),
    "mean_Slope_3p_xy":     ("Slope_3p_xy", "mean"),
    "mean_Slope_3p_xz":     ("Slope_3p_xz", "mean"),
    # Mean track energy (3p)
    "mean_TrackEnergy_3p_xy": ("TrackEnergy_3p_xy", "mean"),
    "mean_TrackEnergy_3p_xz": ("TrackEnergy_3p_xz", "mean"),
    # Mean expected position on 4th plane (from 3p extrapolation)
    "mean_ExpectedPosition_OnPlane4th_xy": ("ExpectedPosition_OnPlane4th_xy", "mean"),
    "mean_ExpectedPosition_OnPlane4th_xz": ("ExpectedPosition_OnPlane4th_xz", "mean"),
    # Mean slope and intercept of 4p tracks
    "mean_Intercept_4p_xy": ("Intercept_4p_xy", "mean"),
    "mean_Intercept_4p_xz": ("Intercept_4p_xz", "mean"),
    "mean_Slope_4p_xy":     ("Slope_4p_xy", "mean"),
    "mean_Slope_4p_xz":     ("Slope_4p_xz", "mean"),
}


def _agg_series(series: pd.Series, func: str) -> float:
    """Apply aggregation func to a single cell that contains an array (or scalar)."""
    val = series
    if hasattr(val, "__len__"):
        arr = np.asarray(val, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return np.nan
        if func == "mean":  return arr.mean()
        if func == "max":   return arr.max()
        if func == "min":   return arr.min()
        if func == "rms":   return float(np.sqrt(np.mean(arr**2)))
    return float(val)


def compute_vector_aggregations(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each entry in VECTOR_AGGREGATIONS, compute the per-event aggregation
    of the vector branch and add it as a new scalar column.
    Returns the input DataFrame with the new columns appended.
    Branches absent from df are silently skipped.
    """
    new_cols = {}
    for new_col, (branch, func) in VECTOR_AGGREGATIONS.items():
        if branch not in df.columns:
            continue
        series = df[branch]
        first_valid = series.dropna().iloc[0] if not series.dropna().empty else None
        if first_valid is not None and np.isscalar(first_valid):
            if func == "rms":
                new_cols[new_col] = series.apply(lambda v: float(np.sqrt(v**2)))
            else:
                new_cols[new_col] = series
        else:
            new_cols[new_col] = series.apply(lambda v: _agg_series(v, func))
    if new_cols:
        df = pd.concat([df, pd.DataFrame(new_cols, index=df.index)], axis=1)
        print(f"  Computed {len(new_cols)} aggregated features from vector branches.")
    return df




def plot_knn_distances(
    X: np.ndarray,
    k: int,
    out_dir: Path,
    eps: float | None = None,
) -> None:
    """
    Sorted k-NN distance plot. The 'elbow' is the natural eps for DBSCAN.
    Points to the right of the elbow are noise candidates.
    """
    from sklearn.neighbors import NearestNeighbors

    nbrs = NearestNeighbors(n_neighbors=k).fit(X)
    distances, _ = nbrs.kneighbors(X)
    kth_dist = np.sort(distances[:, -1])[::-1]

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(kth_dist, color="#4C72B0", linewidth=1.2)
    if eps is not None:
        ax.axhline(eps, color="#C44E52", linestyle="--", linewidth=1,
                   label=f"current eps = {eps}")
        ax.legend(frameon=False)
    ax.set_xlabel("Events (sorted by distance)")
    ax.set_ylabel(f"Distance to {k}-th nearest neighbour")
    ax.set_title(f"k-NN distance plot  (k={k})  —  elbow → optimal eps")
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    fname = out_dir / f"DBSCAN_knn_distances_k{k}.pdf"
    fig.savefig(fname)
    plt.close(fig)
    print(f"Saved: {fname}")


def save_labeled_events(
    pca_df: pd.DataFrame,
    labels: np.ndarray,
    algorithm: str,
    out_dir: Path,
) -> None:
    """
    Save a parquet file with PC coordinates + cluster label for every event.
    Can be reloaded later with pd.read_parquet() for downstream analysis
    without re-running the full PCA pipeline.
    """
    out = pca_df.copy()
    out[f"cluster_{algorithm}"] = labels
    fname = out_dir / f"labeled_events_{algorithm}.parquet"
    out.to_parquet(fname, index=True)
    print(f"Saved: {fname}  ({len(out)} events, columns: {list(out.columns)})")


def plot_feature_distributions_by_cluster(
    raw_df: pd.DataFrame,
    labels: np.ndarray,
    features: list,
    feature_labels: dict,
    algorithm: str,
    out_dir: Path,
    top_n: int = 8,
    prefix: str = "feature_distributions",
) -> None:
    """
    For the top_n most-used features (by column order), plot overlapping
    histograms for each cluster label including noise (-1).
    Saves two PDFs: one with density (normalised) and one with counts in log-y scale.
    """
    cmap = plt.get_cmap("tab10")
    unique_labels = np.unique(labels)
    selected = features[:top_n]
    ncols = 2
    nrows = (top_n + 1) // ncols

    for density, log_y, suffix in [
        (True,  False, ""),
        (False, True,  "_logy"),
    ]:
        fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 5, nrows * 3.2))
        axes = axes.flatten()

        for idx, feat in enumerate(selected):
            ax = axes[idx]
            all_data = raw_df[feat].dropna().values
            bin_edges = np.linspace(all_data.min(), all_data.max(), 51)
            for lbl in unique_labels:
                mask = labels == lbl
                data = raw_df.loc[mask, feat].dropna().values
                color = "lightgray" if lbl == -1 else cmap(lbl % 10)
                name = f"Noise (n={mask.sum()})" if lbl == -1 else f"Cluster {lbl} (n={mask.sum()})"
                ax.hist(data, bins=bin_edges, density=density, alpha=0.55,
                        color=color, label=name, histtype="stepfilled", linewidth=0.5)
            ax.set_xlabel(feature_labels.get(feat, feat), fontsize=9)
            ax.set_ylabel("Density" if density else "Counts", fontsize=8)
            if log_y:
                ax.set_yscale("log")
            ax.tick_params(labelsize=7)
            ax.legend(fontsize=7, frameon=False)
            ax.grid(True, linestyle="--", alpha=0.25)

        for ax in axes[top_n:]:
            ax.set_visible(False)

        title_suffix = " [log scale]" if log_y else ""
        fig.suptitle(f"Feature distributions by cluster — {algorithm}{title_suffix}", fontsize=11)
        fig.tight_layout()
        fname = out_dir / f"{prefix}{suffix}_{algorithm}.pdf"
        fig.savefig(fname)
        plt.close(fig)
        print(f"Saved: {fname}")


def plot_cluster_profile_heatmap(
    raw_df: pd.DataFrame,
    labels: np.ndarray,
    features: list,
    feature_labels: dict,
    algorithm: str,
    out_dir: Path,
) -> None:
    """
    Heatmap of z-score normalised mean feature value per cluster.
    Rows = features, columns = cluster labels.
    Makes immediately visible which features separate the groups.
    """
    from scipy.stats import zscore

    unique_labels = np.unique(labels)
    col_names = []
    means = []

    for lbl in unique_labels:
        mask = labels == lbl
        name = "Noise" if lbl == -1 else f"Cluster {lbl}"
        col_names.append(f"{name}\n(n={mask.sum()})")
        means.append(raw_df.loc[mask, features].mean().values)

    matrix = np.array(means).T          # shape (n_features, n_clusters)
    # z-score across clusters (row-wise)
    with np.errstate(invalid="ignore"):
        matrix_z = zscore(matrix, axis=1)
    matrix_z = np.nan_to_num(matrix_z)  # constant features → 0

    ylabels = [feature_labels.get(f, f) for f in features]
    fig_h = max(6, 0.3 * len(features))
    fig, ax = plt.subplots(figsize=(max(4, 1.5 * len(col_names)), fig_h))

    im = ax.imshow(matrix_z, aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
    plt.colorbar(im, ax=ax, label="Z-score (across clusters)")

    ax.set_xticks(range(len(col_names)))
    ax.set_xticklabels(col_names, fontsize=9)
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.set_title(f"Cluster mean profile — {algorithm}", fontsize=11)

    fig.tight_layout()
    fname = out_dir / f"cluster_profile_{algorithm}.pdf"
    fig.savefig(fname)
    plt.close(fig)
    print(f"Saved: {fname}")


def plot_delta_t_by_cluster(
    timestamps: np.ndarray,
    labels: np.ndarray,
    algorithm: str,
    out_dir: Path,
) -> None:
    """
    Plot the inter-event time (ΔT = t[i+1] - t[i]) distribution per cluster.
    Events are sorted by timestamp before computing differences.
    An exponential fit (Poisson-process reference) is overlaid with fit parameters
    and chi-squared goodness-of-fit annotated on the plot.

    Saves two PDFs:
      - delta_t_<algorithm>.pdf          (linear x-axis)
      - delta_t_log_<algorithm>.pdf      (log x-axis — easier to see tail structure)

    Note: the absolute value of `timestamp` may carry a run-level offset (known
    firmware bug), but *differences* between events are reliable.
    """
    from scipy.stats import expon, chi2 as chi2_dist

    order = np.argsort(timestamps)
    ts_sorted = timestamps[order]
    lbl_sorted = labels[order]

    delta_t = np.diff(ts_sorted)       # ΔT[i] = t[i+1] - t[i]
    lbl_dt = lbl_sorted[1:]            # assign ΔT to the cluster of the arriving event

    unique_labels = np.unique(labels)
    cmap = plt.get_cmap("tab10")

    # Collect per-cluster data and fit results so we can draw both axes
    cluster_data = {}
    for lbl in unique_labels:
        mask = lbl_dt == lbl
        dt_lbl = delta_t[mask]
        dt_lbl = dt_lbl[dt_lbl > 0]
        if dt_lbl.size < 10:
            continue
        color = "lightgray" if lbl == -1 else cmap(lbl % 10)
        name = f"Noise (n={int(mask.sum())})" if lbl == -1 else f"Cluster {lbl} (n={int(mask.sum())})"

        # MLE exponential fit (loc fixed to 0)
        _, scale = expon.fit(dt_lbl, floc=0)
        lam = 1.0 / scale   # rate λ

        # Chi-squared goodness-of-fit using equal-width bins (linear)
        n_bins = min(50, max(10, dt_lbl.size // 30))
        bin_edges_lin = np.linspace(0, np.percentile(dt_lbl, 99), n_bins + 1)
        observed, _ = np.histogram(dt_lbl, bins=bin_edges_lin)
        expected = (np.diff(expon.cdf(bin_edges_lin, loc=0, scale=scale))
                    * dt_lbl.size)
        # Only include bins with expected >= 5 to keep chi2 valid
        valid = expected >= 5
        if valid.sum() > 1:
            chi2_val = float(np.sum((observed[valid] - expected[valid])**2
                                    / expected[valid]))
            dof = int(valid.sum()) - 1   # 1 fitted parameter (λ)
            pval = float(1.0 - chi2_dist.cdf(chi2_val, dof))
        else:
            chi2_val, dof, pval = np.nan, 0, np.nan

        cluster_data[lbl] = dict(
            dt=dt_lbl, color=color, name=name,
            scale=scale, lam=lam,
            chi2=chi2_val, dof=dof, pval=pval,
        )

    def _draw_ax(ax, log_x: bool, density: bool = True) -> None:
        annotation_y = 0.97
        for lbl, d in cluster_data.items():
            dt_lbl = d["dt"]
            lo = np.log10(dt_lbl.min())
            hi = np.log10(dt_lbl.max())
            if log_x:
                bins = np.logspace(lo, hi, 60)
                x_fit = np.logspace(lo, hi, 400)
            else:
                p99 = np.percentile(dt_lbl, 99)
                bins = np.linspace(0, p99, 60)
                x_fit = np.linspace(0, p99, 400)

            ax.hist(dt_lbl, bins=bins, density=density, alpha=0.40,
                    color=d["color"], label=d["name"],
                    histtype="stepfilled", linewidth=0.5)

            # Scale fit curve: density=True → pdf, density=False → counts per bin
            y_fit = expon.pdf(x_fit, loc=0, scale=d["scale"])
            if not density:
                bin_width = np.diff(bins).mean()
                y_fit = y_fit * dt_lbl.size * bin_width
            ax.plot(x_fit, y_fit,
                    color=d["color"], linewidth=2.0, linestyle="--", alpha=0.95)

            # Annotate fit results
            chi2_str = (f"χ²/dof = {d['chi2']:.1f}/{d['dof']},  p = {d['pval']:.3f}"
                        if np.isfinite(d['chi2']) else "χ² n/a")
            label_str = (f"{d['name'].split('(')[0].strip()}:  "
                         f"λ = {d['lam']:.3g} s⁻¹,  "
                         f"⟨ΔT⟩ = {d['scale']:.3g} s\n"
                         f"  {chi2_str}")
            ax.annotate(label_str,
                        xy=(0.02, annotation_y), xycoords="axes fraction",
                        fontsize=7.5, color=d["color"],
                        verticalalignment="top",
                        bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                  ec=d["color"], alpha=0.7))
            annotation_y -= 0.18

    # --- Linear-scale plot (density) ---
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    _draw_ax(ax1, log_x=False, density=True)
    ax1.set_xlabel("ΔT between consecutive events (s)", fontsize=10)
    ax1.set_ylabel("Density", fontsize=10)
    ax1.set_title(f"Inter-event time distribution — {algorithm}", fontsize=11)
    ax1.legend(fontsize=8, frameon=False)
    ax1.grid(True, linestyle="--", alpha=0.3)
    fig1.tight_layout()
    fname1 = out_dir / f"delta_t_{algorithm}.pdf"
    fig1.savefig(fname1)
    plt.close(fig1)
    print(f"Saved: {fname1}")

    # --- Linear-scale plot (counts) ---
    fig3, ax3 = plt.subplots(figsize=(8, 5))
    _draw_ax(ax3, log_x=False, density=False)
    ax3.set_xlabel("ΔT between consecutive events (s)", fontsize=10)
    ax3.set_ylabel("Counts", fontsize=10)
    ax3.set_title(f"Inter-event time distribution (counts) — {algorithm}", fontsize=11)
    ax3.legend(fontsize=8, frameon=False)
    ax3.grid(True, linestyle="--", alpha=0.3)
    fig3.tight_layout()
    fname3 = out_dir / f"delta_t_counts_{algorithm}.pdf"
    fig3.savefig(fname3)
    plt.close(fig3)
    print(f"Saved: {fname3}")

    # --- Log-scale plot (density) ---
    fig2, ax2 = plt.subplots(figsize=(8, 5))
    _draw_ax(ax2, log_x=True)
    ax2.set_xscale("log")
    ax2.set_xlabel("ΔT between consecutive events (s)  [log scale]", fontsize=10)
    ax2.set_ylabel("Density", fontsize=10)
    ax2.set_title(f"Inter-event time distribution (log x) — {algorithm}", fontsize=11)
    ax2.legend(fontsize=8, frameon=False)
    ax2.grid(True, linestyle="--", alpha=0.3, which="both")
    fig2.tight_layout()
    fname2 = out_dir / f"delta_t_log_{algorithm}.pdf"
    fig2.savefig(fname2)
    plt.close(fig2)
    print(f"Saved: {fname2}")


def run_kmeans(
    X: np.ndarray,
    pca_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    features: list,
    feature_labels: dict,
    k: int,
    n_cluster_pcs: int,
    out_dir: Path,
    xlim=None,
    ylim=None,
    top_n: int = 8,
    extras_df: pd.DataFrame = None,
    extra_labels: dict = None,
    unused_df: pd.DataFrame = None,
    unused_labels: dict = None,
    timestamps: np.ndarray = None,
) -> None:
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km_labels = km.fit_predict(X)
    counts = {lbl: int((km_labels == lbl).sum()) for lbl in np.unique(km_labels)}
    tag = f"KMeans_k{k}"
    print(f"  K-Means (k={k}): {counts}")
    plot_clusters(pca_df, km_labels, tag, out_dir, xlim, ylim)
    plot_pc_pairs(pca_df, n_cluster_pcs, km_labels, tag, out_dir)
    plot_feature_distributions_by_cluster(raw_df, km_labels, features,
                                          feature_labels, tag, out_dir, top_n=top_n)
    plot_cluster_profile_heatmap(raw_df, km_labels, features,
                                 feature_labels, tag, out_dir)
    if extras_df is not None:
        extra_cols = list(extras_df.columns)
        plot_feature_distributions_by_cluster(
            extras_df, km_labels, extra_cols, extra_labels or {},
            tag, out_dir, top_n=len(extra_cols), prefix="extra_feature_distributions"
        )
    if unused_df is not None:
        unused_cols = list(unused_df.columns)
        plot_feature_distributions_by_cluster(
            unused_df, km_labels, unused_cols, unused_labels or {},
            tag, out_dir, top_n=len(unused_cols), prefix="unused_feature_distributions"
        )
    if timestamps is not None:
        plot_delta_t_by_cluster(timestamps, km_labels, tag, out_dir)


def run_dbscan(
    X: np.ndarray,
    pca_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    features: list,
    feature_labels: dict,
    eps: float,
    min_samples: int,
    n_cluster_pcs: int,
    out_dir: Path,
    knn_k: int = None,
    xlim=None,
    ylim=None,
    top_n: int = 8,
    extras_df: pd.DataFrame = None,
    extra_labels: dict = None,
    unused_df: pd.DataFrame = None,
    unused_labels: dict = None,
    timestamps: np.ndarray = None,
) -> None:
    from sklearn.cluster import DBSCAN
    plot_knn_distances(X, k=knn_k if knn_k is not None else min_samples, out_dir=out_dir, eps=eps)
    db = DBSCAN(eps=eps, min_samples=min_samples)
    db_labels = db.fit_predict(X)
    n_cls = len(set(db_labels) - {-1})
    n_noise = int((db_labels == -1).sum())
    tag = f"DBSCAN_eps{eps}"
    print(f"  DBSCAN (eps={eps}, min_samples={min_samples}): "
          f"{n_cls} clusters, {n_noise} noise events")
    plot_clusters(pca_df, db_labels, tag, out_dir, xlim, ylim)
    plot_pc_pairs(pca_df, n_cluster_pcs, db_labels, tag, out_dir)
    plot_feature_distributions_by_cluster(raw_df, db_labels, features,
                                          feature_labels, tag, out_dir, top_n=top_n)
    plot_cluster_profile_heatmap(raw_df, db_labels, features,
                                 feature_labels, tag, out_dir)
    if extras_df is not None:
        extra_cols = list(extras_df.columns)
        plot_feature_distributions_by_cluster(
            extras_df, db_labels, extra_cols, extra_labels or {},
            tag, out_dir, top_n=len(extra_cols), prefix="extra_feature_distributions"
        )
    if unused_df is not None:
        unused_cols = list(unused_df.columns)
        plot_feature_distributions_by_cluster(
            unused_df, db_labels, unused_cols, unused_labels or {},
            tag, out_dir, top_n=len(unused_cols), prefix="unused_feature_distributions"
        )
    if timestamps is not None:
        plot_delta_t_by_cluster(timestamps, db_labels, tag, out_dir)


def run_gmm(
    X: np.ndarray,
    pca_df: pd.DataFrame,
    raw_df: pd.DataFrame,
    features: list,
    feature_labels: dict,
    n_components: int,
    covariance_type: str,
    n_cluster_pcs: int,
    out_dir: Path,
    xlim=None,
    ylim=None,
    top_n: int = 8,
    extras_df: pd.DataFrame = None,
    extra_labels: dict = None,
    unused_df: pd.DataFrame = None,
    unused_labels: dict = None,
    timestamps: np.ndarray = None,
) -> None:
    """
    Gaussian Mixture Model clustering.
    Unlike K-Means, GMM assigns soft probabilities to each event;
    here we use the hard assignment (argmax) for plotting.
    Also saves a BIC/AIC plot to help choose n_components.
    """
    from sklearn.mixture import GaussianMixture

    # --- Fit and predict ---
    gmm = GaussianMixture(n_components=n_components, covariance_type=covariance_type,
                          random_state=42, n_init=3)
    gmm_labels = gmm.fit_predict(X)
    tag = f"GMM_k{n_components}_{covariance_type}"
    counts = {lbl: int((gmm_labels == lbl).sum()) for lbl in np.unique(gmm_labels)}
    print(f"  GMM (k={n_components}, cov={covariance_type}): {counts}")
    print(f"    BIC={gmm.bic(X):.1f}  AIC={gmm.aic(X):.1f}")
    plot_clusters(pca_df, gmm_labels, tag, out_dir, xlim, ylim)
    plot_pc_pairs(pca_df, n_cluster_pcs, gmm_labels, tag, out_dir)
    plot_feature_distributions_by_cluster(raw_df, gmm_labels, features,
                                          feature_labels, tag, out_dir, top_n=top_n)
    plot_cluster_profile_heatmap(raw_df, gmm_labels, features,
                                 feature_labels, tag, out_dir)
    if extras_df is not None:
        extra_cols = list(extras_df.columns)
        plot_feature_distributions_by_cluster(
            extras_df, gmm_labels, extra_cols, extra_labels or {},
            tag, out_dir, top_n=len(extra_cols), prefix="extra_feature_distributions"
        )
    if unused_df is not None:
        unused_cols = list(unused_df.columns)
        plot_feature_distributions_by_cluster(
            unused_df, gmm_labels, unused_cols, unused_labels or {},
            tag, out_dir, top_n=len(unused_cols), prefix="unused_feature_distributions"
        )
    if timestamps is not None:
        plot_delta_t_by_cluster(timestamps, gmm_labels, tag, out_dir)
    k_range = range(1, min(n_components + 4, 11))
    bics, aics = [], []
    for k in k_range:
        g = GaussianMixture(n_components=k, covariance_type=covariance_type,
                            random_state=42, n_init=3)
        g.fit(X)
        bics.append(g.bic(X))
        aics.append(g.aic(X))

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(list(k_range), bics, "o-", color="#4C72B0", label="BIC")
    ax.plot(list(k_range), aics, "s--", color="#C44E52", label="AIC")
    ax.axvline(n_components, color="gray", linestyle=":", linewidth=1,
               label=f"current k={n_components}")
    ax.set_xlabel("Number of components")
    ax.set_ylabel("Score (lower = better)")
    ax.set_title(f"GMM model selection ({covariance_type} covariance)")
    ax.legend(frameon=False)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    fname = out_dir / f"GMM_bic_aic_{covariance_type}.pdf"
    fig.savefig(fname)
    plt.close(fig)
    print(f"Saved: {fname}")


def plot_pc_pairs(
    pca_df: pd.DataFrame,
    n_components: int,
    labels: np.ndarray,
    algorithm: str,
    out_dir: Path,
) -> None:
    """Grid of all 2D projections PCi vs PCj coloured by cluster label."""
    pcs = [f"PC{i+1}" for i in range(n_components)]
    n = len(pcs)
    cmap = plt.get_cmap("tab10")
    unique_labels = np.unique(labels)

    fig, axes = plt.subplots(n - 1, n - 1, figsize=(2.8 * (n - 1), 2.8 * (n - 1)))
    # Make axes always 2D array
    if n - 1 == 1:
        axes = np.array([[axes]])

    for row in range(n - 1):       # y axis: PC2 … PCn
        for col in range(n - 1):   # x axis: PC1 … PC(n-1)
            ax = axes[row][col]
            pc_x = pcs[col]
            pc_y = pcs[row + 1]

            if col > row:
                ax.set_visible(False)
                continue

            for lbl in unique_labels:
                mask = labels == lbl
                if lbl == -1:
                    ax.scatter(pca_df.loc[mask, pc_x], pca_df.loc[mask, pc_y],
                               s=2, alpha=0.15, color="lightgray", rasterized=True)
                else:
                    ax.scatter(pca_df.loc[mask, pc_x], pca_df.loc[mask, pc_y],
                               s=2, alpha=0.35, color=cmap(lbl % 10), rasterized=True)

            if row == n - 2:
                ax.set_xlabel(pc_x, fontsize=9)
            else:
                ax.set_xticklabels([])
            if col == 0:
                ax.set_ylabel(pc_y, fontsize=9)
            else:
                ax.set_yticklabels([])

            ax.tick_params(labelsize=7)
            ax.grid(True, linestyle="--", alpha=0.25)

    # Legend on the first visible axes (top-left)
    legend_handles = []
    for lbl in unique_labels:
        color = "lightgray" if lbl == -1 else cmap(lbl % 10)
        name = "Noise" if lbl == -1 else f"Cluster {lbl}"
        legend_handles.append(
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                       markersize=6, label=name)
        )
    axes[0][0].legend(handles=legend_handles, fontsize=7, frameon=False,
                      loc="upper right", markerscale=1.2)

    fig.suptitle(f"PC pair plots – {algorithm}", fontsize=11, y=1.01)
    fig.tight_layout()
    fname = out_dir / f"PCA_pairs_{algorithm}.pdf"
    fig.savefig(fname, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {fname}")


def plot_clusters(
    pca_df: pd.DataFrame,
    labels: np.ndarray,
    algorithm: str,
    out_dir: Path,
    xlim=None,
    ylim=None,
) -> None:
    """Scatter PC1 vs PC2 coloured by cluster label."""
    unique_labels = np.unique(labels)
    n_clusters = len(unique_labels[unique_labels >= 0])
    n_noise = int((labels == -1).sum())

    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(7, 5.5))

    for lbl in unique_labels:
        mask = labels == lbl
        if lbl == -1:
            ax.scatter(pca_df.loc[mask, "PC1"], pca_df.loc[mask, "PC2"],
                       s=4, alpha=0.2, color="lightgray", label="Noise")
        else:
            color = cmap(lbl % 10)
            ax.scatter(pca_df.loc[mask, "PC1"], pca_df.loc[mask, "PC2"],
                       s=6, alpha=0.5, color=color, label=f"Cluster {lbl}")

    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    ax.set_xlabel(r"$\mathrm{PC}_1$")
    ax.set_ylabel(r"$\mathrm{PC}_2$")
    title = f"{algorithm} – {n_clusters} cluster(s)"
    if n_noise:
        title += f", {n_noise} noise events"
    ax.set_title(title)
    ax.legend(loc="upper right", markerscale=2, frameon=False, fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()

    fname = out_dir / f"PCA_clusters_{algorithm}.pdf"
    fig.savefig(fname)
    plt.close(fig)
    print(f"Saved: {fname}")


def plot_explained_variance(pca, out_dir: Path) -> None:
    """Scree plot: individual and cumulative explained variance."""
    evr = pca.explained_variance_ratio_
    cumulative = np.cumsum(evr)
    n = len(evr)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(range(1, n + 1), evr * 100, color="#4C72B0", alpha=0.85, label="Individual")
    ax.plot(range(1, n + 1), cumulative * 100, "o-", color="#C44E52",
            linewidth=1.5, markersize=4, label="Cumulative")
    ax.axhline(90, color="gray", linestyle="--", linewidth=0.8, alpha=0.7)
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Explained variance (%)")
    ax.set_title("Scree plot – explained variance")
    ax.set_xticks(range(1, n + 1))
    ax.legend(frameon=False)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "PCA_explained_variance.pdf")
    plt.close(fig)
    print(f"Saved: {out_dir / 'PCA_explained_variance.pdf'}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="PCA analysis of MURAVES ROOT output")
    parser.add_argument(
        "file_path",
        nargs="*",
        default=[],
        help="Path(s) to one or more ROOT files. Multiple files are concatenated. "
             "If omitted, use --run-range or the built-in default (run2500).",
    )
    parser.add_argument(
        "--run-range",
        nargs=2,
        type=int,
        metavar=("START", "END"),
        dest="run_range",
        default=None,
        help="Inclusive run number range to load, e.g. --run-range 2500 2600. "
             "Files are resolved using --run-dir and --run-pattern.",
    )
    parser.add_argument(
        "--run-dir",
        default=DEFAULT_RUN_DIR,
        dest="run_dir",
        help=f"Directory containing run files (default: {DEFAULT_RUN_DIR})",
    )
    parser.add_argument(
        "--run-pattern",
        default=DEFAULT_RUN_PATTERN,
        dest="run_pattern",
        help=f"Filename pattern with {{run}} placeholder "
             f"(default: {DEFAULT_RUN_PATTERN})",
    )
    parser.add_argument(
        "--outdir",
        default="/user/abiolchi/muraves_outputs/pca_analysis",
        help="Output directory for plots",
    )
    parser.add_argument(
        "--n-components",
        type=int,
        default=2,
        help="Number of PCA components (default: 2)",
    )
    # --- Clustering: which algorithms to run ---
    parser.add_argument(
        "--clustering",
        nargs="+",
        choices=["kmeans", "dbscan", "gmm"],
        default=[],
        metavar="ALG",
        help="Clustering algorithms to run: kmeans, dbscan, gmm (default: none). "
             "Example: --clustering kmeans dbscan gmm",
    )
    # K-Means parameters
    parser.add_argument(
        "--kmeans-k",
        type=int,
        default=3,
        help="Number of clusters for K-Means (default: 3)",
    )
    # DBSCAN parameters
    parser.add_argument(
        "--dbscan-eps",
        type=float,
        default=1.5,
        dest="dbscan_eps",
        help="DBSCAN neighbourhood radius (default: 1.5)",
    )
    parser.add_argument(
        "--dbscan-min-samples",
        type=int,
        default=50,
        dest="dbscan_min_samples",
        help="DBSCAN minimum points per neighbourhood (default: 50)",
    )
    parser.add_argument(
        "--dbscan-k",
        type=int,
        default=None,
        dest="dbscan_k",
        help="k for the k-NN distance plot used to choose eps (default: same as --dbscan-min-samples)",
    )
    # GMM parameters
    parser.add_argument(
        "--gmm-k",
        type=int,
        default=3,
        help="Number of Gaussian components for GMM (default: 3)",
    )
    parser.add_argument(
        "--gmm-covariance",
        default="full",
        choices=["full", "tied", "diag", "spherical"],
        dest="gmm_covariance",
        help="GMM covariance type (default: full)",
    )
    parser.add_argument(
        "--cluster-pcs",
        type=int,
        default=None,
        dest="cluster_pcs",
        help="Number of PCA components to use as input to the clustering algorithms "
             "(default: min(5, --n-components)). Must be <= --n-components.",
    )
    parser.add_argument(
        "--feat-dist-top-n",
        type=int,
        default=None,
        dest="feat_dist_top_n",
        help="Number of features to show in distribution plots (default: all features)",
    )
    parser.add_argument(
        "--aggregate-vectors",
        action="store_true",
        dest="aggregate_vectors",
        help="Compute aggregated features from vector branches (mean/max/rms) "
             "and add them to the PCA feature set.",
    )
    parser.add_argument(
        "--plot-extra-features",
        action="store_true",
        dest="plot_extra_features",
        help="After clustering, plot per-cluster distributions of aggregated vector "
             "features (mean/max/rms of cluster sizes, energies, track residuals) "
             "even when --aggregate-vectors is not active. Useful to check whether "
             "a cluster corresponds to events without a reconstructed track.",
    )
    parser.add_argument(
        "--plot-unused-features",
        action="store_true",
        dest="plot_unused_features",
        help="After clustering, plot per-cluster distributions of branches not used "
             "in the PCA: timestamp, BestChi, 4p quality flags, mean cluster positions, "
             "mean cluster Texp, mean track energy, mean slope/intercept, mean 4p displacement. "
             "See unused_branches.txt for the full list.",
    )
    parser.add_argument(
        "--plot-delta-t",
        action="store_true",
        dest="plot_delta_t",
        help="After clustering, plot the inter-event time (ΔT) distribution per cluster "
             "using the 'timestamp' branch. ΔT is computed between consecutive events "
             "sorted by timestamp. An exponential fit (Poisson-process reference) is "
             "overlaid. Note: absolute timestamps have a run-level offset (known firmware "
             "bug), but differences between events are reliable.",
    )
    parser.add_argument(
        "--track-events-only",
        action="store_true",
        dest="track_events_only",
        help="Keep only events where a best 3p-track was reconstructed "
             "(Theta_3p != -1, ~29 999 events). "
             "Output saved in 'track_events_only/' subdirectory.",
    )
    parser.add_argument(
        "--four-plane-only",
        action="store_true",
        dest="four_plane_only",
        help="Keep only events where a best 4p-track was reconstructed "
             "(Theta_4p != -1, ~1 084 events). "
             "These events have hits on all 4 planes. "
             "Output saved in 'four_plane_only/' subdirectory. "
             "Can be combined with --track-events-only (applies both filters).",
    )
    args = parser.parse_args()

    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build list of files to load
    file_paths = list(args.file_path)  # explicit positional args
    if args.run_range is not None:
        start_run, end_run = args.run_range
        for run in range(start_run, end_run + 1):
            candidate = Path(args.run_dir) / args.run_pattern.format(run=run)
            if candidate.exists():
                file_paths.append(str(candidate))
            else:
                print(f"  Warning: run {run} not found, skipping ({candidate})")
    if not file_paths:
        file_paths = [DEFAULT_ROOT_FILE]
    # Deduplicate preserving order
    seen: set = set()
    file_paths = [p for p in file_paths if not (p in seen or seen.add(p))]

    print(f"Loading {len(file_paths)} file(s)...")
    df = load_multiple_root_files(file_paths)
    print(f"Events loaded: {len(df)}")

    # Optionally compute aggregations from vector branches
    if args.aggregate_vectors:
        print("Computing vector aggregations...")
        df = compute_vector_aggregations(df)

    # Keep only branches listed in FEATURES_LABEL that are actually scalar
    candidate_features = [col for col in df.columns if col in FEATURES_LABEL]
    FEATURES = [
        col for col in candidate_features
        if pd.api.types.is_numeric_dtype(df[col]) and is_scalar_series(df[col])
    ]

    dropped = sorted(set(candidate_features) - set(FEATURES))
    if dropped:
        print("Dropping non-scalar / non-numeric features:", ", ".join(dropped))

    if not FEATURES:
        raise ValueError("No scalar numeric features available for PCA.")

    print(f"Features used for PCA ({len(FEATURES)}): {FEATURES}")

    # Separate original scalar features from aggregated ones.
    # - Original scalars: drop events with any NaN (detector/DAQ issue).
    # - Aggregated features: NaN means "no object reconstructed" → fill with 0.
    aggregated_features = list(VECTOR_AGGREGATIONS.keys()) if args.aggregate_vectors else []
    original_features = [f for f in FEATURES if f not in aggregated_features]
    agg_in_features = [f for f in FEATURES if f in aggregated_features]

    df_work = df[FEATURES].copy()
    if agg_in_features:
        df_work[agg_in_features] = df_work[agg_in_features].fillna(0)

    df_clean = df_work.dropna(subset=original_features)
    n_dropped = len(df) - len(df_clean)
    if n_dropped:
        print(f"Dropped {n_dropped} events with NaN in original scalar features.")

    # --track-events-only: keep only events where a best 3p-track was reconstructed.
    # The sentinel value for "no track" is -1 in Theta_3p (and BestTrack_3p_ChiSquare_*).
    if args.track_events_only:
        if "Theta_3p" not in df_clean.columns:
            raise ValueError(
                "--track-events-only requires Theta_3p to be present in the feature set "
                "(check FEATURES_LABEL)."
            )
        has_track = df_clean["Theta_3p"] != -1
        n_before = len(df_clean)
        df_clean = df_clean[has_track]
        print(f"Track-events-only filter: kept {len(df_clean)}/{n_before} events "
              f"with a reconstructed 3p-track (Theta_3p != -1).")
        out_dir = out_dir / "track_events_only"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output redirected to: {out_dir}")

    # --four-plane-only: keep only events where a best 4p-track was reconstructed,
    # i.e. hits on all 4 planes. Sentinel for "no 4p-track" is -1 in Theta_4p.
    if args.four_plane_only:
        if "Theta_4p" not in df_clean.columns:
            raise ValueError(
                "--four-plane-only requires Theta_4p to be present in the feature set "
                "(check FEATURES_LABEL)."
            )
        has_4p = df_clean["Theta_4p"] != -1
        n_before = len(df_clean)
        df_clean = df_clean[has_4p]
        print(f"Four-plane filter: kept {len(df_clean)}/{n_before} events "
              f"with a reconstructed 4p-track (Theta_4p != -1).")
        out_dir = out_dir / "four_plane_only"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output redirected to: {out_dir}")

    from pca_mapper import PCAMapper

    pca_mapper = PCAMapper(
        raw_df=df_clean,
        features=FEATURES,
        feature_labels=FEATURES_LABEL,
        n_components=args.n_components,
    ).fit()

    evr = pca_mapper.pca.explained_variance_ratio_
    for i, r in enumerate(evr, 1):
        print(f"  PC{i}: {r*100:.2f}%  (cumulative: {evr[:i].sum()*100:.2f}%)")

    # --- Scree plot ---
    plot_explained_variance(pca_mapper.pca, out_dir)

    # --- Density hexbin with top arrows ---
    top_features = [
        "Nclusters_Y1", "Nclusters_Z1",
        "Ntracks_3p_xy", "Ntracks_3p_xz",
        "BestTrack_3p_ChiSquare_xy", "BestTracks_ScatteringAngle_xy",
        "Theta_3p", "Phi_3p",
    ]
    top_features = [f for f in top_features if f in FEATURES]

    fig, _ = pca_mapper.plot_pca_density_hexbin(
        gridsize=60,
        show_contours=False,
        features=top_features,
        figname=str(out_dir / "PCA_density_hexbin.pdf"),
    )
    plt.close(fig)
    print(f"Saved: {out_dir / 'PCA_density_hexbin.pdf'}")

    # --- Component loadings ---
    for pc in [f"PC{i+1}" for i in range(args.n_components)]:
        fig, _ = pca_mapper.plot_pca_component_loadings(
            pc,
            features_label=FEATURES_LABEL,
            top_n=15,
            figname=str(out_dir / f"PCA_{pc}_loadings.pdf"),
        )
        plt.close(fig)
        print(f"Saved: {out_dir / f'PCA_{pc}_loadings.pdf'}")

    # --- Optional clustering ---
    if args.clustering:
        if args.cluster_pcs is not None:
            if args.cluster_pcs > args.n_components:
                raise ValueError(
                    f"--cluster-pcs ({args.cluster_pcs}) cannot exceed "
                    f"--n-components ({args.n_components})."
                )
            N_CLUSTER_PCS = args.cluster_pcs
        else:
            N_CLUSTER_PCS = min(5, args.n_components)
        X_cluster = pca_mapper.pca_df[[f"PC{i+1}" for i in range(N_CLUSTER_PCS)]].values
        feat_dist_top_n = args.feat_dist_top_n if args.feat_dist_top_n is not None else len(FEATURES)
        print(f"\nClustering on first {N_CLUSTER_PCS} PCs...")

        # Build extras_df: aggregated vector features on the same events used for PCA.
        # NaN (= no track/cluster) is filled with 0 so every event has a value.
        # We must draw from the original `df` (all branches), filtered to df_clean's index.
        extras_df = None
        extra_labels = None
        if args.plot_extra_features:
            print("Computing extra aggregated features for post-clustering analysis...")
            df_for_extras = df.loc[df_clean.index].copy()
            extras_raw = compute_vector_aggregations(df_for_extras)
            extra_cols = list(VECTOR_AGGREGATIONS.keys())
            extras_df = extras_raw[extra_cols].fillna(0).reset_index(drop=True)
            extra_labels = {k: k.replace("_", " ") for k in extra_cols}

        # Build timestamps array for ΔT analysis.
        timestamps = None
        if args.plot_delta_t:
            if "timestamp" in df.columns:
                timestamps = df.loc[df_clean.index, "timestamp"].values
                print(f"Timestamps loaded for ΔT analysis ({len(timestamps)} events).")
            else:
                print("Warning: 'timestamp' branch not found in ROOT file — "
                      "--plot-delta-t will be skipped.")

        # Build unused_df: all branches not used in PCA, computed dynamically.
        unused_df = None
        unused_labels = None
        if args.plot_unused_features:
            print("Building unused-branch DataFrame for post-clustering plots...")
            vector_agg_sources = {branch for branch, _ in VECTOR_AGGREGATIONS.values()}
            df_orig = df.loc[df_clean.index].copy()
            unused_df, unused_labels = build_unused_dataframe(
                df_orig, FEATURES, vector_agg_sources
            )
            if unused_df is not None:
                print(f"  {len(unused_df.columns)} unused branches available for plotting.")
            else:
                print("  No unused branches found.")

        if "kmeans" in args.clustering:
            kmeans_dir = out_dir / "kmeans"
            kmeans_dir.mkdir(parents=True, exist_ok=True)
            run_kmeans(
                X_cluster, pca_mapper.pca_df, pca_mapper.raw_df,
                FEATURES, FEATURES_LABEL,
                k=args.kmeans_k,
                n_cluster_pcs=N_CLUSTER_PCS,
                out_dir=kmeans_dir,
                xlim=pca_mapper._xlim, ylim=pca_mapper._ylim,
                top_n=feat_dist_top_n,
                extras_df=extras_df,
                extra_labels=extra_labels,
                unused_df=unused_df,
                unused_labels=unused_labels,
                timestamps=timestamps,
            )

        if "dbscan" in args.clustering:
            dbscan_dir = out_dir / "dbscan"
            dbscan_dir.mkdir(parents=True, exist_ok=True)
            run_dbscan(
                X_cluster, pca_mapper.pca_df, pca_mapper.raw_df,
                FEATURES, FEATURES_LABEL,
                eps=args.dbscan_eps,
                min_samples=args.dbscan_min_samples,
                n_cluster_pcs=N_CLUSTER_PCS,
                out_dir=dbscan_dir,
                knn_k=args.dbscan_k,
                xlim=pca_mapper._xlim, ylim=pca_mapper._ylim,
                top_n=feat_dist_top_n,
                extras_df=extras_df,
                extra_labels=extra_labels,
                unused_df=unused_df,
                unused_labels=unused_labels,
                timestamps=timestamps,
            )

        if "gmm" in args.clustering:
            gmm_dir = out_dir / "gmm"
            gmm_dir.mkdir(parents=True, exist_ok=True)
            run_gmm(
                X_cluster, pca_mapper.pca_df, pca_mapper.raw_df,
                FEATURES, FEATURES_LABEL,
                n_components=args.gmm_k,
                covariance_type=args.gmm_covariance,
                n_cluster_pcs=N_CLUSTER_PCS,
                out_dir=gmm_dir,
                xlim=pca_mapper._xlim, ylim=pca_mapper._ylim,
                top_n=feat_dist_top_n,
                extras_df=extras_df,
                extra_labels=extra_labels,
                unused_df=unused_df,
                unused_labels=unused_labels,
                timestamps=timestamps,
            )

    print("Done.")