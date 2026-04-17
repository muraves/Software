# muoscope/viz/base.py

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
import numpy as np

#from muoscope.utils.utils import VIZ_PARAMS


class BasePlotter:
    """
    Base class for all plotting utilities.

    Responsibilities:
    - Apply consistent matplotlib styling
    - Create figures and axes
    - Handle common plot finalization
    - Save figures

    This class is deliberately data-agnostic.
    """

    def __init__(self, style: dict | None = None) -> None:
        """
        Initialize the plotter and apply matplotlib style.

        Args:
            style: Dictionary of matplotlib rcParams.
                   Defaults to VIZ_PARAMS.
        """
        self.style = style or {}
        self._apply_style()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------

    def _apply_style(self) -> None:
        """Apply matplotlib rcParams."""
        plt.rcParams.update(plt.rcParamsDefault)
        plt.rcParams.update(self.style)

    # ------------------------------------------------------------------
    # Figure / Axes creation
    # ------------------------------------------------------------------

    def create_figure(
        self,
        nrows: int = 1,
        ncols: int = 1,
        *,
        figsize: tuple[float, float] | None = None,
        sharex: bool = False,
        sharey: bool = False,
        height_ratios: list[float] | None = None,
    ) -> tuple[Figure, np.ndarray]:
        """
        Create a matplotlib figure and axes.

        Args:
            nrows: Number of rows.
            ncols: Number of columns.
            figsize: Figure size in inches.
            sharex: Share x-axis.
            sharey: Share y-axis.
            height_ratios: Optional height ratios (for pull plots).

        Returns:
            (Figure, axes array)
        """
        gridspec_kw = {}
        if height_ratios is not None:
            gridspec_kw["height_ratios"] = height_ratios

        fig, axes = plt.subplots(
            nrows=nrows,
            ncols=ncols,
            figsize=figsize,
            sharex=sharex,
            sharey=sharey,
            gridspec_kw=gridspec_kw if gridspec_kw else None,
        )

        # Normalize axes to ndarray
        if isinstance(axes, Axes):
            axes = np.array([axes])

        return fig, axes

    # ------------------------------------------------------------------
    # Axes finalization
    # ------------------------------------------------------------------

    def finalize_axes(
        self,
        ax: Axes,
        *,
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
        grid: bool = True,
        legend: bool = True,
    ) -> None:
        """
        Apply common formatting to an axis.

        Args:
            ax: Matplotlib axis.
            title: Axis title.
            xlabel: X-axis label.
            ylabel: Y-axis label.
            grid: Whether to show grid.
            legend: Whether to show legend.
        """
        if title:
            ax.set_title(title)

        if xlabel:
            ax.set_xlabel(xlabel)

        if ylabel:
            ax.set_ylabel(ylabel)

        if grid:
            ax.grid(True, linestyle="--", alpha=0.6)

        if legend:
            ax.legend()

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save(
        self,
        fig: Figure,
        path: str | Path,
        *,
        dpi: int = 150,
    ) -> None:
        """
        Save figure to disk.

        Args:
            fig: Matplotlib Figure.
            path: Output file path.
            dpi: Resolution.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
