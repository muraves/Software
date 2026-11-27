# tracking/tracking_pipeline_adapter.py

from __future__ import annotations

from simReco_muraves.models.tracking_event import TrackingEvent
from simReco_muraves.models.tracking_results import TrackingResult

from simReco_muraves.tracking.reconstruction_adapter import (
    reconstruct_event,
)


def run_tracking_pipeline(
    events: list[TrackingEvent],
    *,
    x_pos: list[float],
    z_add: list[float],
    y_add: list[float],
    sigma_z: float,
    sigma_y: float,
    proximity_cut_xz: float,
    proximity_cut_xy: float,
    tracking_cfg: dict,
    strips_cfg: dict | None = None,
) -> list[TrackingResult]:
    """
    Run MURAVES tracking reconstruction on the events the caller built
    (build_tracking_events), returning one TrackingResult per event, in
    the same order. The events are passed in, rather than rebuilt here
    from the clusters, so that each caller pairs results with the very
    events they came from (review point A8 of PR #26).
    """

    results: list[TrackingResult] = []

    for event in events:

        result = reconstruct_event(
            event=event,
            x_pos=x_pos,
            z_add=z_add,
            y_add=y_add,
            sigma_z=sigma_z,
            sigma_y=sigma_y,
            proximity_cut_xz=proximity_cut_xz,
            proximity_cut_xy=proximity_cut_xy,
            tracking_cfg=tracking_cfg,
            strips_cfg=strips_cfg,
        )

        results.append(result)

    return results
