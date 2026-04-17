import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from typing import Optional, Dict, List, Tuple

import matplotlib as mpl
from matplotlib.colors import LogNorm
import string

try:
    # Package import path (e.g. when run from project root)
    from dev.pca_analysis.base import BasePlotter
except ModuleNotFoundError:
    # Local fallback (e.g. when run directly from this folder)
    from base import BasePlotter

class PCAMapper:
    """
    Lightweight PCA wrapper for raw detector data exploration.
    """

    def __init__(
        self,
        raw_df: pd.DataFrame,
        features: List[str],
        feature_labels: Optional[Dict[str, str]] = None,
        n_components: int = 2,
    ):
        self.raw_df = raw_df.reset_index(drop=True)
        self.features = features

        if feature_labels is not None:
            self.feature_labels = feature_labels
        else:
            self.feature_labels: Dict[str, str] = {f: f for f in features}

        self.n_components = n_components

        self.scaler = StandardScaler()
        self.pca = PCA(n_components=n_components)

        self.pca_df: Optional[pd.DataFrame] = None

        self.plotter = BasePlotter()

    @property
    def pca_loadings(self) -> pd.DataFrame:

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted")

        return pd.DataFrame(
            self.pca.components_.T,
            index=self.features,
            columns=[f"PC{i+1}" for i in range(self.pca.n_components_)]
        )

    def pca_constraint_to_feature_constraint(
        self,
        pc_index: int,
        threshold: float,
        feature_names: list[str],
        top_k: int = 10,
    ) -> dict:
        """
        Translate a PCA constraint (PC_k > threshold) into a linear
        constraint in the original feature space.

        Returns interpretability-friendly information.
        """

        # --- PCA loading for this component
        w = self.pca.components_[pc_index]
        mu = self.scaler.mean_
        sigma = self.scaler.scale_

        coef = w / sigma
        rhs = threshold + np.sum((w / sigma) * mu)

        # --- Build interpretable table
        df = pd.DataFrame({
            "feature": feature_names,
            "coefficient": coef,
            "abs_contribution": np.abs(coef),
        }).sort_values("abs_contribution", ascending=False)

        return {
            "inequality": f"Σ coef_i * x_i > {rhs:.3f}",
            "offset": rhs,
            "coefficients": coef,
            "top_features": df.head(top_k),
            "full_table": df,
        }

    # ------------------------------------------------------------------
    # Fit & projection
    # ------------------------------------------------------------------
    def fit(self):
        X = self.raw_df[self.features].values
        Xs = self.scaler.fit_transform(X)
        Xp = self.pca.fit_transform(Xs)

        self.pca_df = pd.DataFrame(
            Xp,
            columns=[f"PC{i+1}" for i in range(self.n_components)],
        )

        if "EventID" in self.raw_df.columns:
            self.pca_df["EventID"] = self.raw_df["EventID"].values
        else:
            self.pca_df["EventID"] = np.arange(len(self.raw_df), dtype=int)

        self._xlim = (
            self.pca_df["PC1"].min(),
            self.pca_df["PC1"].max(),
        )
        self._ylim = (
            self.pca_df["PC2"].min(),
            self.pca_df["PC2"].max(),
        )

        return self

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def query_region(
        self,
        condition: pd.Series,
        quantile: float = 0.95,
    ) -> dict:
        """
        Return PCA region occupied by events matching a condition.
        """

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted")

        sel = self.pca_df[condition.values]

        if sel.empty:
            raise ValueError("No events satisfy condition")

        x = sel["PC1"].values
        y = sel["PC2"].values

        ql = (1 - quantile) / 2
        qh = 1 - ql

        return {
            "points": sel,
            "centroid": (x.mean(), y.mean()),
            "bounds": {
                "PC1": np.quantile(x, [ql, qh]),
                "PC2": np.quantile(y, [ql, qh]),
            },
            "n_events": len(sel),
        }

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------
    def plot(
        self,
        colored_by: Optional[str] = None,
        class_colors: Optional[dict] = None,
        ax=None,
        alpha: float = 0.6,
    ):
        """
        Scatter plot of PCA projection.
        """

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted")

        if ax is None:
            fig, ax = plt.subplots(figsize=(6, 5))

        if colored_by and colored_by in self.pca_df.columns:
            for val, df in self.pca_df.groupby(colored_by):
                color = class_colors.get(val, "black") if class_colors else None
                ax.scatter(
                    df["PC1"],
                    df["PC2"],
                    s=15,
                    alpha=alpha,
                    label=str(val),
                    color=color,
                )
            ax.legend(
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False
            )
        else:
            ax.scatter(
                self.pca_df["PC1"],
                self.pca_df["PC2"],
                s=15,
                alpha=alpha,
            )

        ax.set_xlabel("PC1")
        ax.set_ylabel("PC2")
        ax.set_title("PCA projection")
        ax.set_xlim(self._xlim)
        ax.set_ylim(self._ylim)
        ax.grid(True, linestyle="--", alpha=0.4)

        return ax

    def plot_region(
        self,
        regions: list[dict],
        show_background: bool = True,
        background_alpha: float = 0.15,
        n_max_per_region: int = 10_000,
        figname: Optional[str] = None,
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Plot multiple non-overlapping regions in PCA space.

        Parameters
        ----------
        regions : list of dict
            Each dict must contain:
                - 'mask' : boolean mask on raw_df
            Optional keys:
                - 'name' : str
                - 'color' : matplotlib color
                - 'alpha' : float
                - 'marker' : str

        ax : matplotlib Axes, optional
            Axis to draw on.

        show_background : bool
            Whether to show all PCA points in gray.

        background_alpha : float
            Transparency of background points.
        """

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted yet.")

        fig, axes = self.plotter.create_figure(figsize=(6.8, 5.6))
        ax = axes[0]

        # --- background
        if show_background:
            ax.scatter(
                self.pca_df["PC1"],
                self.pca_df["PC2"],
                c="lightgray",
                s=10,
                alpha=background_alpha,
                # label="All events",
            )

        # --- plot each region
        for region in regions:
            mask = region["mask"]

            name = region.get("name", "Region")
            color = region.get("color", "red")
            alpha = region.get("alpha", 0.9)
            marker = region.get("marker", "o")
            size = region.get("size", 25)

            idx = self.raw_df.index[mask]
            pca_sub = self.pca_df.loc[idx]
            n = min(n_max_per_region, len(pca_sub))

            pca_sample = pca_sub.sample(n=n, random_state=66)

            ax.scatter(
                pca_sample["PC1"],
                pca_sample["PC2"],
                label=name,
                c=color,
                alpha=alpha,
                s=size,
                marker=marker,
            )

        # --- styling
        self.plotter.finalize_axes(
            ax,
            xlabel=r"$\mathrm{PC}_1$",
            ylabel=r"$\mathrm{PC}_2$",
            legend=False,
        )

        ax.legend(
            loc="center left", bbox_to_anchor=(1.02, 0.5),
            frameon=False, markerscale=1.4, handletextpad=0.2,
            labelspacing=0.3, fontsize=11
        )
        # --- enforce shared limits
        ax.set_xlim(self._xlim)
        ax.set_ylim(self._ylim)

        ax.tick_params(
            axis="both",
            which="major",
            labelsize=11,
            direction="in",
            top=True,
            right=True,
        )
        if figname is not None:
            self.plotter.save(fig, figname)

        return fig, ax

    def plot_pca_component_loadings(
        self,
        pca_vector: str = "PC1",
        features_label: Optional[Dict[str, str]] = None,
        top_n: int = 10,
        spacing: float = .7,
        figname: Optional[str] = None,
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Physics-style horizontal bar plot of PCA loadings using BasePlotter.
        """

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted")

        # --- Select and sort loadings by absolute magnitude ---
        loadings = self.pca_loadings[pca_vector]
        loadings = loadings.reindex(
            loadings.abs().sort_values(ascending=False).index
        ).head(top_n)

        # Sort for visual clarity (small -> large)
        loadings = loadings.sort_values()

        # --- Labels ---
        if features_label is not None:
            labels = [features_label.get(idx, idx) for idx in loadings.index]
        else:
            labels = loadings.index.tolist()

        # --- Y positions with spacing ---
        y_pos = np.arange(len(labels)) * spacing

        # --- Colors (physics-friendly, colorblind-safe) ---
        pos_color = "#4C72B0"
        neg_color = "#C44E52"
        colors = [neg_color if v < 0 else pos_color for v in loadings.values]

        # --- Adaptive figure size ---
        fig_height = 0.45 * len(labels) + 1.2
        fig, axes = self.plotter.create_figure(figsize=(6.8, fig_height))
        ax = axes[0]

        # --- Plot ---
        ax.barh(y_pos, loadings.values, color=colors, height=0.6)
        ax.axvline(0, color="black", linewidth=0.9)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)

        # --- Symmetric x-limits (physics convention) ---
        max_val = np.max(np.abs(loadings.values))
        ax.set_xlim(-1.1 * max_val, 1.1 * max_val)

        # --- Annotate values (physics papers love numbers) ---
        for i, v in enumerate(loadings.values):
            offset = 0.03 * max_val
            ax.text(
                v + offset if v > 0 else v - offset,
                y_pos[i],
                f"{v:.2f}",
                va="center",
                ha="left" if v > 0 else "right",
                fontsize=12,
            )

        # Largest magnitude on top
        ax.invert_yaxis()

        # Set limit
        ax.set_xlim(
            ax.get_xlim()[0] - (5 * offset),
            ax.get_xlim()[1] + (5 * offset),
        )

        # --- Final formatting via BasePlotter ---
        self.plotter.finalize_axes(
            ax,
            title=f"{pca_vector} loadings",
            xlabel="PCA loading",
            ylabel=None,
            legend=False,
        )

        fig.tight_layout()

        if figname is not None:
            self.plotter.save(fig, figname)

        return fig, ax

    def plot_pca_density_hexbin(
        self,
        gridsize: int = 80,
        log: bool = True,
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        show_contours: bool = True,
        mask: Optional[np.ndarray] = None,
        figname: Optional[str] = None,
        features: Optional[list[str]] = None,
        arrow_scale: float = 1.8,
        max_arrows: int = 12,
    ) -> Tuple[plt.Figure, plt.Axes]:

        if self.pca_df is None:
            raise RuntimeError("PCA not fitted")

        fig, axes = self.plotter.create_figure(figsize=(6.8, 5.6))
        ax = axes[0]

        # ------------------------------------------------------------
        # Mask
        # ------------------------------------------------------------
        if mask is None:
            mask = np.ones(len(self.pca_df), dtype=bool)

        x = self.pca_df.loc[mask, "PC1"]
        y = self.pca_df.loc[mask, "PC2"]
        # ------------------------------------------------------------
        # Density background (hexbin)
        # ------------------------------------------------------------
        cmap = "plasma"
        norm = LogNorm(vmin=vmin, vmax=vmax) if log else None

        hb = ax.hexbin(
            x, y,
            gridsize=gridsize,
            cmap=cmap,
            norm=norm,
            mincnt=1,
            linewidths=0,
        )

        cbar = plt.colorbar(hb, ax=ax, pad=0.02)
        cbar.set_label(r"$N_{\mathrm{events}}$", fontsize=18)

        if show_contours:
            from scipy.ndimage import gaussian_filter

            counts = hb.get_array()
            verts = hb.get_offsets()

            xi = np.linspace(self._xlim[0], self._xlim[1], gridsize)
            yi = np.linspace(self._ylim[0], self._ylim[1], gridsize)
            zi = np.zeros((gridsize, gridsize))

            for (vx, vy), c in zip(verts, counts):
                ix = np.searchsorted(xi, vx) - 1
                iy = np.searchsorted(yi, vy) - 1
                if 0 <= ix < gridsize and 0 <= iy < gridsize:
                    zi[iy, ix] += c

            zi = gaussian_filter(zi, sigma=1.2)

            ax.contour(xi, yi, zi, levels=5, colors="white", linewidths=0.8, alpha=0.7)

        loadings = self.pca_loadings[["PC1", "PC2"]]

        if features is None:
            importance = np.sqrt(loadings["PC1"]**2 + loadings["PC2"]**2)
            features = importance.sort_values(ascending=False).head(max_arrows).index.tolist()
        else:
            features = [f for f in features if f in loadings.index][:max_arrows]

        scale_x = 0.25 * (self._xlim[1] - self._xlim[0])
        scale_y = 0.25 * (self._ylim[1] - self._ylim[0])

        legend_entries = []
        letters = list(string.ascii_uppercase)

        for k, f in enumerate(features):
            vx, vy = loadings.loc[f, "PC1"], loadings.loc[f, "PC2"]

            dx = vx * scale_x * arrow_scale
            dy = vy * scale_y * arrow_scale

            letter = letters[k]
            color = "lime"
            # arrow
            ax.arrow(
                0, 0, dx, dy,
                color=color,
                width=0.002,
                head_width=0.2,
                length_includes_head=True,
                alpha=0.95,
                zorder=10,
            )

            # letter label
            ax.text(
                dx * 1.28,
                dy * 1.28,
                letter,
                color=color,
                fontsize=15,
                fontweight="bold",
                ha="center",
                va="center",
                zorder=11,
            )

            # legend text
            feat_label = self.feature_labels.get(f, f)
            legend_entries.append(f"{letter}: {feat_label}")

        # ------------------------------------------------------------
        # Legend (feature mapping)
        # ------------------------------------------------------------
        if legend_entries:
            legend_text = "\n".join(legend_entries)
            ax.text(
                .2, 0.98,
                legend_text,
                transform=ax.transAxes,
                fontsize=13,
                va="top",
                ha="left",
                bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"),
            )

        # ------------------------------------------------------------
        # Axes style (HEP-like)
        # ------------------------------------------------------------
        ax.set_xlim(self._xlim)
        ax.set_ylim(self._ylim)

        ax.tick_params(
            axis="both",
            which="major",
            labelsize=11,
            direction="in",
            top=True,
            right=True,
        )

        self.plotter.finalize_axes(
            ax,
            xlabel=r"$\mathrm{PC}_1$",
            ylabel=r"$\mathrm{PC}_2$",
            legend=False,
        )

        fig.tight_layout()

        if figname is not None:
            self.plotter.save(fig, figname)

        return fig, ax
