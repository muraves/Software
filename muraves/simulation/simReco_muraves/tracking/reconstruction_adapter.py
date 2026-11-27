# tracking/reconstruction_adapter.py

from __future__ import annotations

from simReco_muraves.models.tracking_results import TrackingResult
from ..models.tracking_event import TrackingEvent
from ..nested_access import MISSING_VALUE, nested_value_or_missing

from muraves_lib.reco.angular_coordinates import TrackAngularCoordinates
from muraves_lib.reco.tracking import MakeTracks

from simReco_muraves.time_expansion import time_expansions


# Plane-4 candidate selection quality, mirroring
# best_track_4p_is_texp_null_* in the experimental MURAVES_reco.py.
TEXP_NULL_NOT_PROMOTED = -1
TEXP_NULL_TRUE = 1
TEXP_NULL_FALSE = 0


def run_tracking_xz(
    event: TrackingEvent,
    x_pos: list[float],
    z_add: list[float],
    sigma_z: float,
    proximity_cut_xz: float,
    tracking_cfg: dict,
    strips_cfg: dict | None = None,
):
    return MakeTracks(
        [c.cluster_position for c in event.z1],
        [c.cluster_position for c in event.z2],
        [c.cluster_position for c in event.z3],
        [c.cluster_position for c in event.z4],
        [c.cluster_energy for c in event.z1],
        [c.cluster_energy for c in event.z2],
        [c.cluster_energy for c in event.z3],
        [c.cluster_energy for c in event.z4],
        # time expansions, not the Geant4 cluster times (B3)
        time_expansions(event.z1),
        time_expansions(event.z2),
        time_expansions(event.z3),
        time_expansions(event.z4),
        proximity_cut_xz,
        x_pos,
        z_add,
        sigma_z,
        tracking_cfg=tracking_cfg,
        strips_cfg=strips_cfg,
    )


def run_tracking_xy(
    event: TrackingEvent,
    x_pos: list[float],
    y_add: list[float],
    sigma_y: float,
    proximity_cut_xy: float,
    tracking_cfg: dict,
    strips_cfg: dict | None = None,
):
    return MakeTracks(
        [c.cluster_position for c in event.y1],
        [c.cluster_position for c in event.y2],
        [c.cluster_position for c in event.y3],
        [c.cluster_position for c in event.y4],
        [c.cluster_energy for c in event.y1],
        [c.cluster_energy for c in event.y2],
        [c.cluster_energy for c in event.y3],
        [c.cluster_energy for c in event.y4],
        # time expansions, not the Geant4 cluster times (B3)
        time_expansions(event.y1),
        time_expansions(event.y2),
        time_expansions(event.y3),
        time_expansions(event.y4),
        proximity_cut_xy,
        x_pos,
        y_add,
        sigma_y,
        tracking_cfg=tracking_cfg,
        strips_cfg=strips_cfg,
    )


# The three functions below copy the best-track selection of the data
# chain (MURAVES_reco.py). They are temporary: #31 moves that selection
# into muraves_lib.reco, where both chains will call the same code, and
# then removes this copy. Until then, keep them as they are.


def _select_best_3p_index(tracks, ntracks_3p: int) -> int:
    """Best three-plane candidate used to seed four-plane promotion.

    Copy of the selection in MURAVES_reco.py, to be replaced by the
    shared one (#31). Both branches currently evaluate to BestChi_index.
    """
    if ntracks_3p <= 0:
        return -1

    if tracks.BestChi_index == tracks.BestEnergy_index:
        return tracks.BestEnergy_index

    return tracks.BestChi_index


def _build_plane4_texp_table(
    cluster_indices_4,
    plane4_texp: list[float],
) -> list[list[float]]:
    """Time expansion of each plane-4 candidate, laid out like
    cluster_indices_4; plane4_texp holds one value per plane-4 cluster.

    Copy of the selection in MURAVES_reco.py, to be replaced by the
    shared one (#31).
    """
    table: list[list[float]] = []

    for row in cluster_indices_4:
        texp_row: list[float] = []

        for idx_val in row:
            idx_int = int(idx_val)

            if 0 <= idx_int < len(plane4_texp):
                texp_row.append(
                    plane4_texp[idx_int]
                )
            else:
                texp_row.append(-1.0)

        table.append(texp_row)

    return table


def _select_plane4_candidate(
    texp_table: list[list[float]],
    parent_row: int,
) -> tuple[int, int]:
    """First plane-4 candidate with a valid Texp, else the first one.

    Returns (selected inner index, texp-null flag). The fallback to
    index 0 when no candidate has a positive Texp is the experimental
    behaviour; the flag records that it happened.

    Copy of the selection in MURAVES_reco.py, to be replaced by the
    shared one (#31).
    """
    selected = 0
    is_texp_null = TEXP_NULL_TRUE

    if 0 <= parent_row < len(texp_table):
        for inner_index, texp in enumerate(texp_table[parent_row]):
            if texp > 0:
                selected = inner_index
                is_texp_null = TEXP_NULL_FALSE
                break

    return selected, is_texp_null


def reconstruct_event(
    event: TrackingEvent,
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
) -> TrackingResult:

    tracks_xz = run_tracking_xz(
        event,
        x_pos,
        z_add,
        sigma_z,
        proximity_cut_xz,
        tracking_cfg,
        strips_cfg,
    )

    tracks_xy = run_tracking_xy(
        event,
        x_pos,
        y_add,
        sigma_y,
        proximity_cut_xy,
        tracking_cfg,
        strips_cfg,
    )

    ntracks_3p_xz = len(tracks_xz.intercepts_3p)
    ntracks_3p_xy = len(tracks_xy.intercepts_3p)

    best_track_xz_index = tracks_xz.BestChi_index
    best_track_xy_index = tracks_xy.BestChi_index

    # --------------------------------------------------
    # 3-plane angular coordinates
    # --------------------------------------------------

    theta_3p = -1.0
    phi_3p = -1.0

    if (
        best_track_xz_index >= 0
        and best_track_xy_index >= 0
        and best_track_xz_index < len(tracks_xz.slopes_3p)
        and best_track_xy_index < len(tracks_xy.slopes_3p)
    ):
        theta_3p, phi_3p = TrackAngularCoordinates(
            tracks_xy.slopes_3p[best_track_xy_index],
            tracks_xz.slopes_3p[best_track_xz_index],
            x_pos[0],
            x_pos[2],
        )

    # =====================================================
    # BEST 4P TRACK SELECTION
    # PORTED FROM MURAVES_reco.py
    # =====================================================

    theta_4p = -1.0
    phi_4p = -1.0

    track_3p_of_4p_idx_xy = -1
    track_3p_of_4p_idx_xz = -1

    track_4p_idx_xy = -1
    track_4p_idx_xz = -1

    best_track_4p_is_texp_null_xz = TEXP_NULL_NOT_PROMOTED
    best_track_4p_is_texp_null_xy = TEXP_NULL_NOT_PROMOTED

    best_track_xy_ind = _select_best_3p_index(
        tracks_xy,
        ntracks_3p_xy,
    )

    best_track_xz_ind = _select_best_3p_index(
        tracks_xz,
        ntracks_3p_xz,
    )

    # ----------------------------------------------
    # Texp tables for plane-4 candidates
    # ----------------------------------------------

    cluster_c4_texp_xz = _build_plane4_texp_table(
        tracks_xz.cluster_indices_4,
        time_expansions(event.z4),
    )

    cluster_c4_texp_xy = _build_plane4_texp_table(
        tracks_xy.cluster_indices_4,
        time_expansions(event.y4),
    )

    # ----------------------------------------------
    # ONLY promote 4p tracks attached to the
    # selected best 3p tracks
    # ----------------------------------------------

    if (
        tracks_xz.Track_3p_to_4p_index
        and tracks_xy.Track_3p_to_4p_index
    ):

        if (
            best_track_xy_ind
            in tracks_xy.Track_3p_to_4p_index
            and
            best_track_xz_ind
            in tracks_xz.Track_3p_to_4p_index
        ):

            track_3p_of_4p_idx_xy = (
                tracks_xy.Track_3p_to_4p_index.index(
                    best_track_xy_ind
                )
            )

            track_3p_of_4p_idx_xz = (
                tracks_xz.Track_3p_to_4p_index.index(
                    best_track_xz_ind
                )
            )

            (
                track_4p_idx_xy,
                best_track_4p_is_texp_null_xy,
            ) = _select_plane4_candidate(
                cluster_c4_texp_xy,
                track_3p_of_4p_idx_xy,
            )

            (
                track_4p_idx_xz,
                best_track_4p_is_texp_null_xz,
            ) = _select_plane4_candidate(
                cluster_c4_texp_xz,
                track_3p_of_4p_idx_xz,
            )

            if (
                track_3p_of_4p_idx_xy
                < len(tracks_xy.slope_4p)
                and
                track_3p_of_4p_idx_xz
                < len(tracks_xz.slope_4p)
                and
                track_4p_idx_xy
                < len(
                    tracks_xy.slope_4p[
                        track_3p_of_4p_idx_xy
                    ]
                )
                and
                track_4p_idx_xz
                < len(
                    tracks_xz.slope_4p[
                        track_3p_of_4p_idx_xz
                    ]
                )
            ):

                theta_4p, phi_4p = (
                    TrackAngularCoordinates(
                        tracks_xy.slope_4p[
                            track_3p_of_4p_idx_xy
                        ][
                            track_4p_idx_xy
                        ],
                        tracks_xz.slope_4p[
                            track_3p_of_4p_idx_xz
                        ][
                            track_4p_idx_xz
                        ],
                        x_pos[0],
                        x_pos[3],
                    )
                )

    # --------------------------------------------------
    # Selected-candidate fit quality
    # --------------------------------------------------

    best_track_3p_chi_square_xz = MISSING_VALUE
    best_track_3p_chi_square_xy = MISSING_VALUE

    if 0 <= best_track_xz_index < len(tracks_xz.chiSquares_3p):
        best_track_3p_chi_square_xz = float(
            tracks_xz.chiSquares_3p[best_track_xz_index]
        )

    if 0 <= best_track_xy_index < len(tracks_xy.chiSquares_3p):
        best_track_3p_chi_square_xy = float(
            tracks_xy.chiSquares_3p[best_track_xy_index]
        )

    best_track_4p_chi_square_xz = nested_value_or_missing(
        tracks_xz.chiSquares_4p,
        track_3p_of_4p_idx_xz,
        track_4p_idx_xz,
    )

    best_track_4p_chi_square_xy = nested_value_or_missing(
        tracks_xy.chiSquares_4p,
        track_3p_of_4p_idx_xy,
        track_4p_idx_xy,
    )

    return TrackingResult(
        process_id=event.process_id,
        event=event.event,
        tracks_xz=tracks_xz,
        tracks_xy=tracks_xy,
        ntracks_3p_xz=ntracks_3p_xz,
        ntracks_3p_xy=ntracks_3p_xy,
        best_track_xz_index=best_track_xz_index,
        best_track_xy_index=best_track_xy_index,
        theta_3p=theta_3p,
        phi_3p=phi_3p,
        theta_4p=theta_4p,
        phi_4p=phi_4p,
        track_3p_of_4p_index_xz=track_3p_of_4p_idx_xz,
        track_3p_of_4p_index_xy=track_3p_of_4p_idx_xy,
        track_4p_index_xz=track_4p_idx_xz,
        track_4p_index_xy=track_4p_idx_xy,
        best_track_3p_chi_square_xz=best_track_3p_chi_square_xz,
        best_track_3p_chi_square_xy=best_track_3p_chi_square_xy,
        best_track_4p_chi_square_xz=best_track_4p_chi_square_xz,
        best_track_4p_chi_square_xy=best_track_4p_chi_square_xy,
        best_track_4p_is_texp_null_xz=best_track_4p_is_texp_null_xz,
        best_track_4p_is_texp_null_xy=best_track_4p_is_texp_null_xy,
    )
