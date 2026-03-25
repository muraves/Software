#!/usr/bin/env python3
"""
MURAVES Main Reconstruction Software – Python version.

Pythonised translation of MURAVES_reco_v2.cpp (and its companion C++ files
ClusterLists.cc, ReadEvent.cc, Tracking.cc, EvaluateAngularCoordinates.cc).

The output ROOT file has exactly the same tree structure and branch names as the
C++ version.

Usage:
    python MURAVES_reco_v2.py <color> <run>
    color : telescope name  (ROSSO | NERO | BLU)
    run   : integer run number
"""

import math
import os
import random
import re
import sys
import time
from array import array

import numpy as np
import ROOT

ROOT.gROOT.SetBatch(True)
ROOT.gErrorIgnoreLevel = ROOT.kError  # suppress info/warning messages


# ─────────────────────────────────────────────────────────────────────────────
# Angular coordinates (EvaluateAngularCoordinates.cc)
# ─────────────────────────────────────────────────────────────────────────────

def track_angular_coordinates(slope_xy, slope_xz, x0, x2):
    """Return [theta, phi] (degrees) from two projected slopes."""
    dz = slope_xz * (x0 - x2)
    dx = x2 - x0
    dy = slope_xy * dx
    theta = math.atan(abs(dz) / math.sqrt(dx * dx + dy * dy)) * (180.0 / math.pi)
    if dz > 0:
        phi = math.atan(slope_xy) * (180.0 / math.pi) + 180.0
    else:
        if slope_xy > 0:
            phi = math.atan(slope_xy) * 180.0 / math.pi
        else:
            phi = 360.0 + math.atan(slope_xy) * 180.0 / math.pi
    return [theta, phi]


# ─────────────────────────────────────────────────────────────────────────────
# Cluster helpers (ClusterLists.cc)
# ─────────────────────────────────────────────────────────────────────────────

def _sort_indices_descending(values):
    """Indices that sort *values* in descending order (mirrors SortIndices)."""
    return sorted(range(len(values)), key=lambda i: values[i], reverse=True)


def create_cluster_list(deposits, thr_cluster, thr_single, thr_adjacent,
                        t_exp1, t_exp2, trigger_mask1, trigger_mask2):
    """
    Build a list of clusters from a 64-strip deposit array.

    Parameters mirror CreateClusterList() arguments:
        deposits        – list[float] of length 64
        thr_cluster     – EnergyThreshold_clusterStrip  (s1)
        thr_single      – EnergyThreshold_singleStrip   (s2)
        thr_adjacent    – AdStripsThEnergy_singleStripCl (s3)
        t_exp1, t_exp2  – time-expansion values for the two half-planes
        trigger_mask1   – strip indices in trigger mask for the lower board
        trigger_mask2   – strip indices in trigger mask for the upper board

    Returns a dict with keys matching ClusterCollection members.
    """
    MAX_STRIP_ENERGY = 3000.0
    FIRST_STRIP_POS = -0.528
    ADJ_DIST = 0.0165
    N_STRIPS = 64
    MIN_ENERGY_TM = 20

    # Accumulator for the current cluster under construction
    clu_en = 0.0
    clu_pos = 0.0
    clu_size = 0
    strip_index = []
    clu_strip_deposits = []
    clu_strip_pos = []
    clu_strip_id = []

    # Finished clusters (unsorted)
    cl_positions = []
    cl_energies = []
    cl_sizes = []
    cl_strips_deposits = []
    cl_strips_positions = []
    cl_strips_id = []

    for st in range(N_STRIPS):
        deposit = deposits[st]
        cluster_is_on = (thr_cluster <= deposit < MAX_STRIP_ENERGY)

        if deposit > MIN_ENERGY_TM:
            if st < 32:
                if st not in trigger_mask1:
                    cluster_is_on = False
            else:
                if (st - 32) not in trigger_mask2:
                    cluster_is_on = False

        if st == N_STRIPS - 1:
            cluster_is_on = False

        if cluster_is_on:
            strip_position = float(st * ADJ_DIST)
            clu_strip_deposits.append(deposit)
            clu_strip_pos.append(FIRST_STRIP_POS + strip_position)
            clu_strip_id.append(st)
            clu_en += deposit
            clu_pos += (strip_position + FIRST_STRIP_POS) * deposit
            clu_size += 1
            strip_index.append(st)
        else:
            # --- handle pending cluster ---
            if clu_size == 1:
                si = strip_index[0]
                if thr_single < clu_en < MAX_STRIP_ENERGY:
                    # try to add post-strip
                    if (si < N_STRIPS - 1
                            and thr_adjacent < deposits[si + 1] < MAX_STRIP_ENERGY):
                        post_pos = float((si + 1) * ADJ_DIST)
                        clu_pos += deposits[si + 1] * (FIRST_STRIP_POS + post_pos)
                        clu_en += deposits[si + 1]
                        clu_size += 1
                        clu_strip_deposits.append(deposits[si + 1])
                        clu_strip_pos.append(FIRST_STRIP_POS + post_pos)
                        clu_strip_id.append(si + 1)
                    # try to add pre-strip
                    if (si > 0
                            and thr_adjacent < deposits[si - 1] < MAX_STRIP_ENERGY):
                        pre_pos = float((si - 1) * ADJ_DIST)
                        clu_pos += deposits[si - 1] * (FIRST_STRIP_POS + pre_pos)
                        clu_en += deposits[si - 1]
                        clu_strip_deposits.append(deposits[si - 1])
                        clu_strip_pos.append(FIRST_STRIP_POS + pre_pos)
                        clu_strip_id.append(si - 1)
                        clu_size += 1
                else:
                    clu_pos = 0.0
                    clu_en = 0.0
                    clu_size = 0

            if clu_size > 0:
                clust_pos = clu_pos / clu_en
                # single-strip: smear randomly within ±half strip-width
                if clu_size == 1:
                    clust_pos += random.uniform(-ADJ_DIST / 2.0, ADJ_DIST / 2.0)
                cl_positions.append(clust_pos)
                cl_energies.append(clu_en)
                cl_sizes.append(clu_size)

                # sort strips within cluster by descending deposit
                ord_idx = _sort_indices_descending(clu_strip_deposits)
                cl_strips_deposits.append([clu_strip_deposits[k] for k in ord_idx])
                cl_strips_positions.append([clu_strip_pos[k] for k in ord_idx])
                cl_strips_id.append([clu_strip_id[k] for k in ord_idx])

            strip_index.clear()
            clu_strip_deposits.clear()
            clu_strip_pos.clear()
            clu_en = 0.0
            clu_pos = 0.0
            clu_size = 0

    # Sort clusters by descending energy
    ord_cl = _sort_indices_descending(cl_energies)
    sorted_positions = [cl_positions[i] for i in ord_cl]
    sorted_energies = [cl_energies[i] for i in ord_cl]
    sorted_sizes = [cl_sizes[i] for i in ord_cl]
    sorted_strips_dep = [cl_strips_deposits[i] for i in ord_cl]
    sorted_strips_pos = [cl_strips_positions[i] for i in ord_cl]
    sorted_strips_id = [cl_strips_id[i] for i in ord_cl]

    # Assign time-expansion per cluster
    boundary1 = FIRST_STRIP_POS + 31 * ADJ_DIST
    boundary2 = FIRST_STRIP_POS + 32 * ADJ_DIST
    texp_cluster = []
    for pos in sorted_positions:
        if pos <= boundary1:
            texp = t_exp1
        elif pos < boundary2:
            texp = t_exp1 if t_exp1 > t_exp2 else t_exp2
        else:
            texp = t_exp2
        texp_cluster.append(texp)

    return {
        "ClustersEnergy":    sorted_energies,
        "ClustersPositions": sorted_positions,
        "ClustersSize":      sorted_sizes,
        "StripsEnergy":      sorted_strips_dep,
        "StripsPositions":   sorted_strips_pos,
        "StripsID":          sorted_strips_id,
        "TimeExpansions":    texp_cluster,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Weighted linear fit (replaces TGraphErrors + TF1 "pol1" in ROOT)
# ─────────────────────────────────────────────────────────────────────────────

def linear_fit_weighted(x_arr, y_arr, sigma):
    """
    Weighted least-squares fit  y = q + m*x  with uniform error *sigma* on y.

    Returns (intercept, slope, chi_square, slope_error, intercept_error).
    Reproduces the result of ROOT's TGraphErrors::Fit("pol1","RQS") when all
    x-errors are zero and all y-errors equal *sigma*.
    """
    n = len(x_arr)
    w = 1.0 / (sigma * sigma)   # common weight

    S = n * w
    Sx = w * sum(x_arr)
    Sy = w * sum(y_arr)
    Sxx = w * sum(xi * xi for xi in x_arr)
    Sxy = w * sum(xi * yi for xi, yi in zip(x_arr, y_arr))

    delta = S * Sxx - Sx * Sx
    intercept = (Sxx * Sy - Sx * Sxy) / delta
    slope = (S * Sxy - Sx * Sy) / delta

    intercept_error = math.sqrt(Sxx / delta)
    slope_error = math.sqrt(S / delta)

    chi_square = sum(
        ((yi - intercept - slope * xi) / sigma) ** 2
        for xi, yi in zip(x_arr, y_arr)
    )
    return intercept, slope, chi_square, slope_error, intercept_error


# ─────────────────────────────────────────────────────────────────────────────
# Event reading (ReadEvent.cc)
# ─────────────────────────────────────────────────────────────────────────────

def read_event(adc_line, strip_indices):
    """
    Parse one tab-separated ADC data line.

    Parameters
    ----------
    adc_line     : str  – one line from the ADC data file
    strip_indices: list[int] – sorted channel indices (sorted_ch in main)

    Returns a dict with keys matching struct_Event members.
    """
    data = adc_line.rstrip("\n").split("\t")

    N_INFO_BOARD = 39
    N_CHANNELS = 32
    N_BOARDS = 16

    boards = []
    all_time_exp = []
    boards_tr_mask_ch = []
    boards_tr_mask_strips = []
    tr_mask_sizes = []

    timestamp = float(data[35])

    for n in range(N_BOARDS):
        base = n * N_INFO_BOARD
        time_exp = float(data[base + 37])
        all_time_exp.append(time_exp)

        # parse trigger-mask string  "_15_14_"  →  [15, 14]
        tr_mask_str = data[base + 39]
        tr_mask_parts = [p for p in tr_mask_str.split("_") if p]
        tr_mask_ch = []
        tr_mask_strips = []
        for part in tr_mask_parts:
            try:
                ch = int(float(part))
                tr_mask_ch.append(ch)
                if ch in strip_indices:
                    tr_mask_strips.append(strip_indices.index(ch))
            except ValueError:
                pass
        boards_tr_mask_ch.append(tr_mask_ch)
        boards_tr_mask_strips.append(tr_mask_strips)
        tr_mask_sizes.append(len(tr_mask_strips))

        # read 32 ADC channels for this board
        all_adc = [float(data[3 + base + ch]) for ch in range(N_CHANNELS)]
        # re-order by strip order
        sorted_adc = [all_adc[strip_indices[idx]] for idx in range(len(strip_indices))]
        boards.append(sorted_adc)

    return {
        "boards":          boards,
        "TrMask_channels": boards_tr_mask_ch,
        "TrMask_strips":   boards_tr_mask_strips,
        "TrMask_size":     tr_mask_sizes,
        "timeStamp":       timestamp,
        "timeExp":         all_time_exp,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Track finding (Tracking.cc)
# ─────────────────────────────────────────────────────────────────────────────

def make_tracks(clusters_1, clusters_2, clusters_3, clusters_4,
                clusters_en_1, clusters_en_2, clusters_en_3, clusters_en_4,
                texp_cl1, texp_cl2, texp_cl3, texp_cl4,
                proximity_cut, x_pos, z_add, sigma):
    """
    Build 3-plane and 4-plane tracks.  Mirrors MakeTracks() in Tracking.cc.

    Parameters
    ----------
    clusters_*   : list[float] – cluster positions (with z-offset already
                                 applied in the main loop below)
    clusters_en_*: list[float] – cluster energies
    texp_cl*     : list[float] – time-expansion values per cluster
    proximity_cut: float       – max residue at plane-2 to accept a track
    x_pos        : list[float] – x (depth) positions of the 4 planes
    z_add        : list[float] – z offsets for the 3 tracking planes
    sigma        : float       – spatial resolution (used as y-error in fit)

    Returns a dict with the same fields as struct TracksCollection.
    """
    FIRST_STRIP_POS = -0.528
    ADJ_DIST = 0.0165
    min_p4 = FIRST_STRIP_POS
    max_p4 = FIRST_STRIP_POS + 63 * ADJ_DIST

    # ── result accumulators ──────────────────────────────────────────────────
    intercept_3p = []
    slope_3p = []
    chi2_3p = []
    idx_cl1 = []
    idx_cl2 = []
    idx_cl3 = []
    pos_c1 = []
    pos_c2 = []
    pos_c3 = []
    res_c1 = []
    res_c2 = []
    res_c3 = []
    track_energy_3p = []
    ntracks_4p = []
    plane4_intercepted = []
    exp_pos_p4 = []
    tracks_3p_index = []
    exp_res_p2_list = []

    is_in_track_cl1 = []       # n tracks using cl1[i]
    is_in_track_cl2 = []
    is_in_track_cl3 = []
    is_in_track_cl1_4p = []
    is_in_track_cl2_4p = []
    is_in_track_cl3_4p = []

    positions_c4 = []
    intercept_4p = []
    slope_4p = []
    chi2_4p = []
    displacement_p4 = []
    cluster_indices_4 = []
    res_c1_p4 = []
    res_c2_p4 = []
    res_c3_p4 = []
    res_c4_p4 = []
    track_energy_4p = []
    scattering_angles = []

    best_chi = 10000.0
    best_energy = 0.0
    best_chi_index = -1
    best_energy_index = -1
    ntracks = 0

    # helper 2-D vectors for "is-in-track" counting
    vv_cl2 = []      # vv_cl2[i_cl1][j_cl2]  = 1 if (cl1_i, cl2_j) is in a 3p track
    vv_cl3 = []      # vv_cl3[i_cl1][k_cl3]
    vv_cl2_4p = []
    vv_cl3_4p = []

    x1 = x_pos[0]
    x2 = x_pos[1]
    x3 = x_pos[2]
    x4 = x_pos[3]

    for i, raw_p1 in enumerate(clusters_1):
        ntrack_cl1 = 0
        ntrack_cl1_4p = 0
        p1 = raw_p1 + z_add[0]

        n_track_cl3_vec = []
        n_track_cl3_vec_4p = []

        for k, raw_p3 in enumerate(clusters_3):
            ntrack_cl3 = 0
            ntrack_cl3_4p = 0
            p3 = raw_p3 + z_add[2]

            n_track_cl2_vec = []
            n_track_cl2_vec_4p = []

            for j, raw_p2 in enumerate(clusters_2):
                p2 = raw_p2 + z_add[1]

                # expected position of p2 from the p1–p3 line
                exp_m = (p1 - p3) / (x1 - x3)
                exp_q = p1 - exp_m * x1
                exp_p2 = exp_m * x2 + exp_q
                exp_res_2 = p2 - exp_p2

                if abs(exp_res_2) < proximity_cut:
                    exp_res_p2_list.append(exp_res_2)
                    ntracks += 1
                    ntrack_cl1 += 1
                    ntrack_cl3 += 1
                    n_track_cl2_vec.append(1)
                    idx_cl1.append(i)
                    idx_cl2.append(j)
                    idx_cl3.append(k)

                    # ── 3-plane linear fit ───────────────────────────────────
                    q3, m3, chi3, m3_err, q3_err = linear_fit_weighted(
                        [x1, x2, x3], [p1, p2, p3], sigma
                    )
                    intercept_3p.append(q3)
                    slope_3p.append(m3)
                    chi2_3p.append(chi3)

                    pos_c1.append(p1)
                    pos_c2.append(p2)
                    pos_c3.append(p3)
                    res_c1.append(p1 - q3 - m3 * x1)
                    res_c2.append(p2 - q3 - m3 * x2)
                    res_c3.append(p3 - q3 - m3 * x3)
                    en3 = clusters_en_1[i] + clusters_en_2[j] + clusters_en_3[k]
                    track_energy_3p.append(en3)

                    # ── best-track selection ─────────────────────────────────
                    if texp_cl1[i] > 0 and texp_cl2[j] > 0 and texp_cl3[k] > 0:
                        if chi3 < best_chi:
                            best_chi = chi3
                            best_chi_index = ntracks - 1
                        if en3 > best_energy:
                            best_energy = en3
                            best_energy_index = ntracks - 1

                    # ── 4th-plane projection ─────────────────────────────────
                    exp_p4 = q3 + m3 * x4
                    exp_p4_err = math.sqrt(q3_err**2 + x4**2 * m3_err**2)

                    if min_p4 - sigma < exp_p4 < max_p4 + sigma:
                        exp_pos_p4.append(exp_p4)
                        plane4_intercepted.append(1)

                        if clusters_4:
                            ntrack_cl3_4p += 1
                            ntrack_cl1_4p += 1
                            n_track_cl2_vec_4p.append(1)
                            tracks_3p_index.append(ntracks - 1)
                        else:
                            n_track_cl2_vec_4p.append(0)

                        # residues of all 4th-plane clusters w.r.t. projected track
                        res_p4_raw = [c - exp_p4 for c in clusters_4]
                        ntracks_4p.append(len(res_p4_raw))

                        # sort 4th-plane clusters by |residue| (smallest first)
                        sorted_cl4_idx = sorted(
                            range(len(res_p4_raw)),
                            key=lambda h: abs(res_p4_raw[h])
                        )
                        sorted_p4 = [clusters_4[h] for h in sorted_cl4_idx]
                        sorted_disp = [res_p4_raw[h] for h in sorted_cl4_idx]

                        single_pos_c4 = []
                        single_int_4p = []
                        single_slp_4p = []
                        single_chi_4p = []
                        single_res_c1_4p = []
                        single_res_c2_4p = []
                        single_res_c3_4p = []
                        single_res_c4_4p = []
                        single_en_4p = []
                        theta_scatter = []

                        for cl4_idx, p4 in enumerate(sorted_p4):
                            q4, m4, chi4, *_ = linear_fit_weighted(
                                [x1, x2, x3, x4],
                                [p1, p2, p3, p4],
                                sigma
                            )
                            single_pos_c4.append(p4)
                            single_int_4p.append(q4)
                            single_slp_4p.append(m4)
                            single_chi_4p.append(chi4)
                            single_res_c1_4p.append(p1 - q4 - m4 * x1)
                            single_res_c2_4p.append(p2 - q4 - m4 * x2)
                            single_res_c3_4p.append(p3 - q4 - m4 * x3)
                            single_res_c4_4p.append(p4 - q4 - m4 * x4)
                            single_en_4p.append(
                                clusters_en_1[i] + clusters_en_2[j]
                                + clusters_en_3[k]
                                + clusters_en_4[sorted_cl4_idx[cl4_idx]]
                            )

                            # scattering angle (law of cosines)
                            disp = sorted_disp[cl4_idx]
                            side_a = math.sqrt(
                                (q3 + x3 * m3 - q3 - x4 * m3) ** 2
                                + (x3 - x4) ** 2
                            )
                            side_b = math.sqrt(
                                (q3 + x3 * m3 - p4) ** 2
                                + (x3 - x4) ** 2
                            )
                            cos_th = (
                                side_a**2 + side_b**2
                                - (q3 + x4 * m3 - p4) ** 2
                            ) / (2 * side_a * side_b)
                            # clamp to [-1, 1] to avoid domain errors
                            cos_th = max(-1.0, min(1.0, cos_th))
                            sign = 1.0 if disp >= 0 else -1.0
                            theta_scatter.append(
                                sign * math.acos(cos_th) * (180.0 / math.pi)
                            )

                        scattering_angles.append(theta_scatter)
                        positions_c4.append(single_pos_c4)
                        intercept_4p.append(single_int_4p)
                        slope_4p.append(single_slp_4p)
                        chi2_4p.append(single_chi_4p)
                        displacement_p4.append(sorted_disp)
                        cluster_indices_4.append(
                            [float(h) for h in sorted_cl4_idx]
                        )
                        res_c1_p4.append(single_res_c1_4p)
                        res_c2_p4.append(single_res_c2_4p)
                        res_c3_p4.append(single_res_c3_4p)
                        res_c4_p4.append(single_res_c4_4p)
                        track_energy_4p.append(single_en_4p)

                    else:
                        plane4_intercepted.append(0)
                        ntracks_4p.append(0)
                        n_track_cl2_vec_4p.append(0)
                else:
                    n_track_cl2_vec.append(0)
                    n_track_cl2_vec_4p.append(0)

            n_track_cl3_vec.append(1 if ntrack_cl3 > 0 else 0)
            n_track_cl3_vec_4p.append(1 if ntrack_cl3_4p > 0 else 0)
            vv_cl2.append(n_track_cl2_vec)
            vv_cl2_4p.append(n_track_cl2_vec_4p)

        vv_cl3.append(n_track_cl3_vec)
        vv_cl3_4p.append(n_track_cl3_vec_4p)
        is_in_track_cl1_4p.append(ntrack_cl1_4p)
        is_in_track_cl1.append(ntrack_cl1)

    # ── count how many tracks each cluster-2 / cluster-3 participates in ─────
    # 3-plane
    if vv_cl3:
        for j in range(len(vv_cl3[0])):
            is_in_track_cl3.append(sum(vv_cl3[i][j] for i in range(len(vv_cl3))))
    if vv_cl2:
        for j in range(len(vv_cl2[0])):
            is_in_track_cl2.append(sum(vv_cl2[i][j] for i in range(len(vv_cl2))))
    # 4-plane
    if vv_cl3_4p:
        for j in range(len(vv_cl3_4p[0])):
            is_in_track_cl3_4p.append(
                sum(vv_cl3_4p[i][j] for i in range(len(vv_cl3_4p)))
            )
    if vv_cl2_4p:
        for j in range(len(vv_cl2_4p[0])):
            is_in_track_cl2_4p.append(
                sum(vv_cl2_4p[i][j] for i in range(len(vv_cl2_4p)))
            )

    return {
        # 3p track parameters
        "intercepts_3p":          intercept_3p,
        "slopes_3p":              slope_3p,
        "chiSquares_3p":          chi2_3p,
        "cluster_index_1":        idx_cl1,
        "cluster_index_2":        idx_cl2,
        "cluster_index_3":        idx_cl3,
        "Ntracks_4p":             ntracks_4p,
        "position_c1":            pos_c1,
        "position_c2":            pos_c2,
        "position_c3":            pos_c3,
        "residue_c1":             res_c1,
        "residue_c2":             res_c2,
        "residue_c3":             res_c3,
        "TrackEnergy_3p":         track_energy_3p,
        # cluster track-membership counters
        "IsInTrack_clusters1":    is_in_track_cl1,
        "IsInTrack_clusters2":    is_in_track_cl2,
        "IsInTrack_clusters3":    is_in_track_cl3,
        "IsInTrack_clusters1_4p": is_in_track_cl1_4p,
        "IsInTrack_clusters2_4p": is_in_track_cl2_4p,
        "IsInTrack_clusters3_4p": is_in_track_cl3_4p,
        # 4p track parameters
        "Plane4th_isIntercepted":     plane4_intercepted,
        "positions_c4":               positions_c4,
        "intercept_4p":               intercept_4p,
        "slope_4p":                   slope_4p,
        "chiSquares_4p":              chi2_4p,
        "displacement_p4":            displacement_p4,
        "cluster_indices_4":          cluster_indices_4,
        "residue_c1_p4":              res_c1_p4,
        "residue_c2_p4":              res_c2_p4,
        "residue_c3_p4":              res_c3_p4,
        "residue_c4_p4":              res_c4_p4,
        "TrackEnergy_4p":             track_energy_4p,
        "ScatteringAngles":           scattering_angles,
        "ExpectedPosition_OnPlane4th": exp_pos_p4,
        "Track_3p_to_4p_index":       tracks_3p_index,
        "Track_3p_ExpectedRes_p2":    exp_res_p2_list,
        # best-track scalars
        "BestChi":         best_chi,
        "BestEnergy":      best_energy,
        "BestChi_index":   best_chi_index,
        "BestEnergy_index": best_energy_index,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ROOT branch utilities
# ─────────────────────────────────────────────────────────────────────────────

def _vd():
    return ROOT.std.vector("double")()

def _vi():
    return ROOT.std.vector("int")()

def _vvd():
    return ROOT.std.vector(ROOT.std.vector("double"))()

def _fill_vd(v, values):
    v.clear()
    for x in values:
        v.push_back(float(x))

def _fill_vi(v, values):
    v.clear()
    for x in values:
        v.push_back(int(x))

def _fill_vvd(vv, values):
    vv.clear()
    for inner in values:
        tmp = ROOT.std.vector("double")()
        for x in inner:
            tmp.push_back(float(x))
        vv.push_back(tmp)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(" ~~~~~~~  Welcome to the MURAVES reconstruction 2.0 ~~~~~~~~  ")
    print("                      .-----. ")
    print("             .----. .'       ' ")
    print("            '      V           '  ")
    print("          '                      ' ")
    print("        '                          '   ")
    print("      '                              ' ")
    print("       _  _        _   _        _  _  ")
    print("      |  V | |  | |_| |_| \\  / |_ |_  ")
    print("      |    | |__| | \\ | |  \\/  |_  _| ")
    print()
    print(" ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  ")

    t_start = time.time()

    # ── command-line arguments ───────────────────────────────────────────────
    if len(sys.argv) < 3:
        print("Usage: python MURAVES_reco_v2.py <color> <run>")
        sys.exit(1)
    color_st = sys.argv[1]
    run = int(sys.argv[2])
    run_string = str(run)

    use_single_run_ped = 1

    # ── geometrical parameters ───────────────────────────────────────────────
    if color_st == "ROSSO":
        z_add = [0.292, 0.251, 0.207, 0.0]
        x_pos = [-0.265, 0.0, 0.262, 1.475]
    elif color_st == "NERO":
        z_add = [0.293, 0.251, 0.210, 0.0]
        x_pos = [-0.26, 0.0, 0.262, 1.492]
    elif color_st == "BLU":
        z_add = [0.2712, 0.2312, 0.1892, 0.0]
        x_pos = [-0.26, 0.0, 0.262, 1.492]
    else:
        print(f"Unknown color: {color_st}")
        sys.exit(1)

    y_add = [0.0, 0.0, 0.0, 0.0]

    sigma_z = 0.0040
    sigma_y = 0.0035

    # ── clustering parameters ────────────────────────────────────────────────
    s1 = 6.0    # cluster-strip energy threshold
    s2 = 10.0   # single-strip cluster energy threshold
    s3 = 2.0    # adjacent-strip energy threshold

    # ── tracking parameters ──────────────────────────────────────────────────
    prox_xz = 5 * sigma_z
    prox_xy = 5 * sigma_y

    # ── output paths ─────────────────────────────────────────────────────────
    SAVING_PATH = f"/workspace/test/RECONSTRUCTED/{color_st}/"
    mini_tree_name = f"{SAVING_PATH}MURAVES_miniRunTree_run{run_string}.root"
    root_file_name = f"{SAVING_PATH}MURAVES_AnalyzedData_run{run_string}.root"

    # ── find the ADC file ────────────────────────────────────────────────────
    adc_prefix = f"/workspace/test/PARSED/{color_st}/ADC_run{run_string}"
    matches = sorted(__import__("glob").glob(adc_prefix + "*"))
    if not matches:
        print(f"ERROR: ADC file not found: {adc_prefix}*")
        sys.exit(1)
    complete_adc_name = matches[0]
    print(f"ADC file: {complete_adc_name}")

    # ── slow-control data ────────────────────────────────────────────────────
    sc_file_path = f"/workspace/test/RAW_GZ/{color_st}/SLOWCONTROL_run{run_string}"
    sc_tr = 0.0
    sc_temperature = 0.0
    sc_wp = 0.0
    try:
        with open(sc_file_path) as sc_f:
            for sc_line in sc_f:
                parts = sc_line.rstrip("\n").split("\t")
                if not parts:
                    continue
                try:
                    if int(float(parts[0])) == run:
                        sc_tr = float(parts[43])
                        sc_temperature = float(parts[3])
                        sc_wp = float(parts[5])
                        break
                except (IndexError, ValueError):
                    continue
    except FileNotFoundError:
        print(f"Warning: slow-control file not found: {sc_file_path}")

    print(f"ANALYZING RUN : {run} OF {color_st} DETECTOR")
    print(f"Clustering parameters:")
    print(f"Single strip min energy: {s1}")
    print(f"Single strip cluster min energy: {s2}")
    print(f"Single strip cluster adiacent strips  min energy: {s3}")
    print(f"Working Point: {sc_wp}  Temperature: {sc_temperature}  Trigger Rate: {sc_tr}")

    w_p = int(sc_wp)

    # ── SPIROC/hybrid map ────────────────────────────────────────────────────
    spiroc_path = "/workspace/Software/tracks_reconstruction/AncillaryFiles/spiroc-hybrid-map.cfg"
    strips_raw = []
    channels_raw = []
    try:
        with open(spiroc_path) as sf:
            for line_idx, line in enumerate(sf):
                if line_idx == 0:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    strips_raw.append(int(parts[0]))
                    channels_raw.append(int(parts[1]))
    except FileNotFoundError:
        print(f"Warning: spiroc map not found: {spiroc_path}")

    # sort by strip number
    strip_indices = sorted(range(len(strips_raw)), key=lambda i: strips_raw[i])
    sorted_ch = [channels_raw[strip_indices[i]] for i in range(len(strip_indices))]

    # ── read pedestals ───────────────────────────────────────────────────────
    N_BOARDS = 16
    if use_single_run_ped == 1:
        ped_dir = f"/workspace/test/PEDESTAL/{color_st}/{run_string}/"
        ped_prefix = f"{ped_dir}pedestal_"
    else:
        ped_prefix = f"config/{color_st}/ped_WP{w_p}/pedestal_"

    boards_peds = []
    boards_one_phes = []
    boards_is1phe_copy = []

    for board_n in range(N_BOARDS):
        ped_file = f"{ped_prefix}{board_n}.cfg"
        peds = []
        one_phes = []
        is_copy = []
        try:
            with open(ped_file) as pf:
                for line_idx, line in enumerate(pf):
                    if line_idx == 0:
                        continue
                    parts = line.split()
                    if len(parts) >= 3:
                        peds.append(float(parts[1]))
                        one_phes.append(float(parts[2]))
                        is_copy.append(0)
        except FileNotFoundError:
            print(f"Warning: pedestal file not found: {ped_file}")
            peds = [0.0] * 32
            one_phes = [1.0] * 32
            is_copy = [0] * 32

        sorted_peds = [peds[sorted_ch[idx]] for idx in range(len(sorted_ch))]
        sorted_one_phes = [one_phes[sorted_ch[idx]] for idx in range(len(sorted_ch))]
        sorted_is_copy = [is_copy[sorted_ch[idx]] for idx in range(len(sorted_ch))]
        boards_peds.append(sorted_peds)
        boards_one_phes.append(sorted_one_phes)
        boards_is1phe_copy.append(sorted_is_copy)

    # ── telescope configuration ───────────────────────────────────────────────
    tel_cfg_path = (
        f"/workspace/Software/tracks_reconstruction/AncillaryFiles/"
        f"telescope{color_st}.cfg"
    )
    n_stations = []
    views = []
    try:
        with open(tel_cfg_path) as tf:
            for line_idx, line in enumerate(tf):
                if line_idx == 0:
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 5:
                    n_stations.append(int(parts[2]))
                    views.append(parts[4])
    except FileNotFoundError:
        print(f"Warning: telescope config not found: {tel_cfg_path}")

    # ── extract date/time from ADC filename ───────────────────────────────────
    datime = ROOT.TDatime()
    date_match = re.search(
        r"_(\d{4})(\d{2})(\d{2})[-_](\d{2})(\d{2})(\d{2})", complete_adc_name
    )
    if date_match:
        y, mt, d, h, mn, s = [int(date_match.group(g)) for g in range(1, 7)]
        datime.Set(y, mt, d, h, mn, s)
    datime.Print()

    # ── create output ROOT file + main tree ───────────────────────────────────
    os.makedirs(SAVING_PATH, exist_ok=True)
    file_root = ROOT.TFile(root_file_name, "recreate")
    tree = ROOT.TTree("AnalyzedData", "A tree to store MURAVES analyzed data")

    # --- branch variables (scalar) ---
    run_arr     = array("i", [run])
    ncl_z1      = array("i", [0]); ncl_z2 = array("i", [0])
    ncl_z3      = array("i", [0]); ncl_z4 = array("i", [0])
    ncl_y1      = array("i", [0]); ncl_y2 = array("i", [0])
    ncl_y3      = array("i", [0]); ncl_y4 = array("i", [0])
    ntr3p_xz    = array("i", [0]); ntr3p_xy = array("i", [0])
    best_chi_xy_arr    = array("d", [0.0])
    best_en_xy_arr     = array("d", [0.0])
    best_chi_xz_arr    = array("d", [0.0])
    best_en_xz_arr     = array("d", [0.0])
    best_chi_xy_idx    = array("i", [0])
    best_en_xy_idx     = array("i", [0])
    best_chi_xz_idx    = array("i", [0])
    best_en_xz_idx     = array("i", [0])
    theta_3p_arr = array("d", [0.0]); phi_3p_arr = array("d", [0.0])
    theta_4p_arr = array("d", [0.0]); phi_4p_arr = array("d", [0.0])
    bt3p_xy_idx  = array("i", [0]); bt3p_xz_idx = array("i", [0])
    t3p_of_4p_xy = array("i", [0]); t3p_of_4p_xz = array("i", [0])
    t4p_idx_xy   = array("i", [0]); t4p_idx_xz   = array("i", [0])
    bt3p_chi_xy  = array("d", [0.0]); bt3p_chi_xz = array("d", [0.0])
    bt4p_chi_xy  = array("d", [0.0]); bt4p_chi_xz = array("d", [0.0])
    bts_scat_xy  = array("d", [0.0]); bts_scat_xz = array("d", [0.0])
    bt4p_texp_null_xz = array("i", [0]); bt4p_texp_null_xy = array("i", [0])
    wp_arr  = array("d", [0.0]); temp_arr = array("d", [0.0])
    trate_arr = array("d", [0.0])

    # --- branch variables (vectors) ---
    cl_size_z1  = _vi(); cl_size_z2  = _vi()
    cl_size_z3  = _vi(); cl_size_z4  = _vi()
    cl_size_y1  = _vi(); cl_size_y2  = _vi()
    cl_size_y3  = _vi(); cl_size_y4  = _vi()
    cl_texp_z1  = _vd(); cl_texp_z2  = _vd()
    cl_texp_z3  = _vd(); cl_texp_z4  = _vd()
    cl_texp_y1  = _vd(); cl_texp_y2  = _vd()
    cl_texp_y3  = _vd(); cl_texp_y4  = _vd()
    cl_en_z1    = _vd(); cl_en_z2    = _vd()
    cl_en_z3    = _vd(); cl_en_z4    = _vd()
    cl_en_y1    = _vd(); cl_en_y2    = _vd()
    cl_en_y3    = _vd(); cl_en_y4    = _vd()
    cl_pos_z1   = _vd(); cl_pos_z2   = _vd()
    cl_pos_z3   = _vd(); cl_pos_z4   = _vd()
    cl_pos_y1   = _vd(); cl_pos_y2   = _vd()
    cl_pos_y3   = _vd(); cl_pos_y4   = _vd()
    st_en_z1    = _vvd(); st_en_z2   = _vvd()
    st_en_z3    = _vvd(); st_en_z4   = _vvd()
    st_en_y1    = _vvd(); st_en_y2   = _vvd()
    st_en_y3    = _vvd(); st_en_y4   = _vvd()
    st_pos_z1   = _vvd(); st_pos_z2  = _vvd()
    st_pos_z3   = _vvd(); st_pos_z4  = _vvd()
    st_pos_y1   = _vvd(); st_pos_y2  = _vvd()
    st_pos_y3   = _vvd(); st_pos_y4  = _vvd()
    st_id_z1    = _vvd(); st_id_z2   = _vvd()
    st_id_z3    = _vvd(); st_id_z4   = _vvd()
    st_id_y1    = _vvd(); st_id_y2   = _vvd()
    st_id_y3    = _vvd(); st_id_y4   = _vvd()
    int_3p_xz   = _vd(); slp_3p_xz  = _vd(); chi_3p_xz  = _vd()
    int_3p_xy   = _vd(); slp_3p_xy  = _vd(); chi_3p_xy  = _vd()
    tcl_z1_idx  = _vi(); tcl_z2_idx = _vi(); tcl_z3_idx = _vi()
    tcl_y1_idx  = _vi(); tcl_y2_idx = _vi(); tcl_y3_idx = _vi()
    tcl_z4_idx  = _vi(); tcl_y4_idx = _vi()
    res_3p_z1   = _vd(); res_3p_z2  = _vd(); res_3p_z3  = _vd()
    res_3p_y1   = _vd(); res_3p_y2  = _vd(); res_3p_y3  = _vd()
    en_3p_xy    = _vd(); en_3p_xz   = _vd()
    p4_int_xy   = _vvd(); p4_slp_xy = _vvd(); p4_chi_xy  = _vvd()
    p4_slp_xz   = _vvd(); p4_chi_xz = _vvd()
    disp_xy     = _vvd(); disp_xz   = _vvd()
    cl4_idx_xy  = _vvd(); cl4_idx_xz = _vvd()
    scat_xy     = _vvd(); scat_xz   = _vvd()
    p4int_xz    = _vvd()
    plane4_xy   = _vi();  plane4_xz = _vi()
    ntr4p_xy    = _vi();  ntr4p_xz  = _vi()
    exp_p4_xy   = _vd();  exp_p4_xz = _vd()
    is_in3p_z1  = _vi(); is_in3p_z2 = _vi(); is_in3p_z3 = _vi()
    is_in3p_z4  = _vi(); is_in3p_y1 = _vi(); is_in3p_y2 = _vi()
    is_in3p_y3  = _vi(); is_in3p_y4 = _vi()
    is_in4p_z1  = _vi(); is_in4p_z2 = _vi(); is_in4p_z3 = _vi()
    is_in4p_z4  = _vi(); is_in4p_y1 = _vi(); is_in4p_y2 = _vi()
    is_in4p_y3  = _vi(); is_in4p_y4 = _vi()
    isbt3p_xy   = _vi(); isbt3p_xz  = _vi()
    tm_strips   = _vvd(); tm_channels = _vvd()
    tm_size     = _vi()

    # ── register branches ────────────────────────────────────────────────────
    tree.Branch("Run", run_arr, "Run/I")
    tree.Branch("Nclusters_Z1", ncl_z1, "Nclusters_Z1/I")
    tree.Branch("Nclusters_Z2", ncl_z2, "Nclusters_Z2/I")
    tree.Branch("Nclusters_Z3", ncl_z3, "Nclusters_Z3/I")
    tree.Branch("Nclusters_Z4", ncl_z4, "Nclusters_Z4/I")
    tree.Branch("Nclusters_Y1", ncl_y1, "Nclusters_Y1/I")
    tree.Branch("Nclusters_Y2", ncl_y2, "Nclusters_Y2/I")
    tree.Branch("Nclusters_Y3", ncl_y3, "Nclusters_Y3/I")
    tree.Branch("Nclusters_Y4", ncl_y4, "Nclusters_Y4/I")

    tree.Branch("ClusterSize_Z1", cl_size_z1)
    tree.Branch("ClusterSize_Z2", cl_size_z2)
    tree.Branch("ClusterSize_Z3", cl_size_z3)
    tree.Branch("ClusterSize_Z4", cl_size_z4)
    tree.Branch("ClusterZ1_Texp", cl_texp_z1)
    tree.Branch("ClusterZ2_Texp", cl_texp_z2)
    tree.Branch("ClusterZ3_Texp", cl_texp_z3)
    tree.Branch("ClusterZ4_Texp", cl_texp_z4)
    tree.Branch("ClusterEnergy_Z1", cl_en_z1)
    tree.Branch("ClusterEnergy_Z2", cl_en_z2)
    tree.Branch("ClusterEnergy_Z3", cl_en_z3)
    tree.Branch("ClusterEnergy_Z4", cl_en_z4)
    tree.Branch("ClusterPosition_Z1", cl_pos_z1)
    tree.Branch("ClusterPosition_Z2", cl_pos_z2)
    tree.Branch("ClusterPosition_Z3", cl_pos_z3)
    tree.Branch("ClusterPosition_Z4", cl_pos_z4)

    tree.Branch("ClusterSize_Y1", cl_size_y1)
    tree.Branch("ClusterSize_Y2", cl_size_y2)
    tree.Branch("ClusterSize_Y3", cl_size_y3)
    tree.Branch("ClusterSize_Y4", cl_size_y4)
    tree.Branch("ClusterY1_Texp", cl_texp_y1)
    tree.Branch("ClusterY2_Texp", cl_texp_y2)
    tree.Branch("ClusterY3_Texp", cl_texp_y3)
    tree.Branch("ClusterY4_Texp", cl_texp_y4)
    tree.Branch("ClusterEnergy_Y1", cl_en_y1)
    tree.Branch("ClusterEnergy_Y2", cl_en_y2)
    tree.Branch("ClusterEnergy_Y3", cl_en_y3)
    tree.Branch("ClusterEnergy_Y4", cl_en_y4)
    tree.Branch("ClusterPosition_Y1", cl_pos_y1)
    tree.Branch("ClusterPosition_Y2", cl_pos_y2)
    tree.Branch("ClusterPosition_Y3", cl_pos_y3)
    tree.Branch("ClusterPosition_Y4", cl_pos_y4)

    tree.Branch("StripsEnergy_Z1", st_en_z1)
    tree.Branch("StripsEnergy_Z2", st_en_z2)
    tree.Branch("StripsEnergy_Z3", st_en_z3)
    tree.Branch("StripsEnergy_Z4", st_en_z4)
    tree.Branch("StripsEnergy_Y1", st_en_y1)
    tree.Branch("StripsEnergy_Y2", st_en_y2)
    tree.Branch("StripsEnergy_Y3", st_en_y3)
    tree.Branch("StripsEnergy_Y4", st_en_y4)
    tree.Branch("StripsPosition_Z1", st_pos_z1)
    tree.Branch("StripsPosition_Z2", st_pos_z2)
    tree.Branch("StripsPosition_Z3", st_pos_z3)
    tree.Branch("StripsPosition_Z4", st_pos_z4)
    tree.Branch("StripsPosition_Y1", st_pos_y1)
    tree.Branch("StripsPosition_Y2", st_pos_y2)
    tree.Branch("StripsPosition_Y3", st_pos_y3)
    tree.Branch("StripsPosition_Y4", st_pos_y4)
    tree.Branch("StripsID_Z1", st_id_z1)
    tree.Branch("StripsID_Z2", st_id_z2)
    tree.Branch("StripsID_Z3", st_id_z3)
    tree.Branch("StripsID_Z4", st_id_z4)
    tree.Branch("StripsID_Y1", st_id_y1)
    tree.Branch("StripsID_Y2", st_id_y2)
    tree.Branch("StripsID_Y3", st_id_y3)
    tree.Branch("StripsID_Y4", st_id_y4)

    # tracking – 3 planes
    tree.Branch("Ntracks_3p_xz", ntr3p_xz, "Ntracks_3p_xz/I")
    tree.Branch("Ntracks_3p_xy", ntr3p_xy, "Ntracks_3p_xy/I")
    tree.Branch("Intercept_3p_xz", int_3p_xz)
    tree.Branch("Slope_3p_xz", slp_3p_xz)
    tree.Branch("chiSquare_3p_xz", chi_3p_xz)
    tree.Branch("Intercept_3p_xy", int_3p_xy)
    tree.Branch("Slope_3p_xy", slp_3p_xy)
    tree.Branch("chiSquare_3p_xy", chi_3p_xy)
    tree.Branch("TrackCluster_z1_index", tcl_z1_idx)
    tree.Branch("TrackCluster_z2_index", tcl_z2_idx)
    tree.Branch("TrackCluster_z3_index", tcl_z3_idx)
    tree.Branch("TrackCluster_y1_index", tcl_y1_idx)
    tree.Branch("TrackCluster_y2_index", tcl_y2_idx)
    tree.Branch("TrackCluster_y3_index", tcl_y3_idx)
    tree.Branch("Residue_Track3p_z1", res_3p_z1)
    tree.Branch("Residue_Track3p_z2", res_3p_z2)
    tree.Branch("Residue_Track3p_z3", res_3p_z3)
    tree.Branch("Residue_Track3p_y1", res_3p_y1)
    tree.Branch("Residue_Track3p_y2", res_3p_y2)
    tree.Branch("Residue_Track3p_y3", res_3p_y3)
    tree.Branch("TrackEnergy_3p_xy", en_3p_xy)
    tree.Branch("TrackEnergy_3p_xz", en_3p_xz)
    tree.Branch("Plane4th_isIntercepted_xz", plane4_xz)
    tree.Branch("Plane4th_isIntercepted_xy", plane4_xy)
    tree.Branch("BestChi_xy_index", best_chi_xy_idx, "BestChi_xy_index/I")
    tree.Branch("BestEnergy_xy_index", best_en_xy_idx, "BestEnergy_xy_index/I")
    tree.Branch("BestChi_xz_index", best_chi_xz_idx, "BestChi_xz_index/I")
    tree.Branch("BestEnergy_xz_index", best_en_xz_idx, "BestEnergy_xz_index/I")
    tree.Branch("BestChi_xy", best_chi_xy_arr, "BestChi_xy/D")
    tree.Branch("BestEnergy_xy", best_en_xy_arr, "BestEnergy_xy/D")
    tree.Branch("BestChi_xz", best_chi_xz_arr, "BestChi_xz/D")
    tree.Branch("BestEnergy_xz", best_en_xz_arr, "BestEnergy_xz/D")
    tree.Branch("ExpectedPosition_OnPlane4th_xy", exp_p4_xy)
    tree.Branch("ExpectedPosition_OnPlane4th_xz", exp_p4_xz)

    # tracking – 4 planes
    tree.Branch("Slope_4p_xz", p4_slp_xz)
    tree.Branch("chiSquare_4p_xz", p4_chi_xz)
    tree.Branch("displacement_p4_xz", disp_xz)
    tree.Branch("Intercept_4p_xy", p4_int_xy)
    tree.Branch("Slope_4p_xy", p4_slp_xy)
    tree.Branch("chiSquare_4p_xy", p4_chi_xy)
    tree.Branch("displacement_p4_xy", disp_xy)
    tree.Branch("cluster_c4_index_xz", cl4_idx_xz)
    tree.Branch("cluster_c4_index_xy", cl4_idx_xy)
    tree.Branch("ScatteringAngle_xy", scat_xy)
    tree.Branch("ScatteringAngle_xz", scat_xz)

    # cluster-is-in-track
    tree.Branch("isInTrack_3p_clZ1", is_in3p_z1)
    tree.Branch("isInTrack_3p_clZ2", is_in3p_z2)
    tree.Branch("isInTrack_3p_clZ3", is_in3p_z3)
    tree.Branch("isInTrack_3p_clZ4", is_in3p_z4)   # not filled (same as C++)
    tree.Branch("isInTrack_3p_clY1", is_in3p_y1)
    tree.Branch("isInTrack_3p_clY2", is_in3p_y2)
    tree.Branch("isInTrack_3p_clY3", is_in3p_y3)
    tree.Branch("isInTrack_3p_clY4", is_in3p_y4)   # not filled (same as C++)
    tree.Branch("isInTrack_4p_clZ1", is_in4p_z1)
    tree.Branch("isInTrack_4p_clZ2", is_in4p_z2)
    tree.Branch("isInTrack_4p_clZ3", is_in4p_z3)
    tree.Branch("isInTrack_4p_clZ4", is_in4p_z4)   # not filled (same as C++)
    tree.Branch("isInTrack_4p_clY1", is_in4p_y1)
    tree.Branch("isInTrack_4p_clY2", is_in4p_y2)
    tree.Branch("isInTrack_4p_clY3", is_in4p_y3)
    tree.Branch("isInTrack_4p_clY4", is_in4p_y4)   # not filled (same as C++)

    # best tracks
    tree.Branch("Theta_3p", theta_3p_arr, "Theta_3p/D")
    tree.Branch("Theta_4p", theta_4p_arr, "Theta_4p/D")
    tree.Branch("Phi_3p", phi_3p_arr, "Phi_3p/D")
    tree.Branch("Phi_4p", phi_4p_arr, "Phi_4p/D")
    tree.Branch("isBestTrack_3p_xy", isbt3p_xy)
    tree.Branch("isBestTrack_3p_xz", isbt3p_xz)
    tree.Branch("BestTrack_3p_xy_index", bt3p_xy_idx, "BestTrack_3p_xy_index/I")
    tree.Branch("BestTrack_3p_xz_index", bt3p_xz_idx, "BestTrack_3p_xz_index/I")
    tree.Branch("Track_3p_of_4p_index_xy", t3p_of_4p_xy, "Track_3p_of_4p_index_xy/I")
    tree.Branch("Track_3p_of_4p_index_xz", t3p_of_4p_xz, "Track_3p_of_4p_index_xz/I")
    tree.Branch("Track_4p_index_xy", t4p_idx_xy, "Track_4p_index_xy/I")
    tree.Branch("Track_4p_index_xz", t4p_idx_xz, "Track_4p_index_xz/I")
    tree.Branch("BestTrack_3p_ChiSquare_xy", bt3p_chi_xy, "BestTrack_3p_ChiSquare_xy/D")
    tree.Branch("BestTrack_3p_ChiSquare_xz", bt3p_chi_xz, "BestTrack_3p_ChiSquare_xz/D")
    tree.Branch("BestTrack_4p_ChiSquare_xy", bt4p_chi_xy, "BestTrack_4p_ChiSquare_xy/D")
    tree.Branch("BestTrack_4p_ChiSquare_xz", bt4p_chi_xz, "BestTrack_4p_ChiSquare_xz/D")
    tree.Branch("BestTracks_ScatteringAngle_xy", bts_scat_xy, "BestTracks_ScatteringAngle_xy/D")
    tree.Branch("BestTracks_ScatteringAngle_xz", bts_scat_xz, "BestTracks_ScatteringAngle_xz/D")
    tree.Branch("Best_track_4p_isTexpNULL_xz", bt4p_texp_null_xz, "Best_track_4p_isTexpNULL_xz/I")
    tree.Branch("Best_track_4p_isTexpNULL_xy", bt4p_texp_null_xy, "Best_track_4p_isTexpNULL_xy/I")

    # other
    tree.Branch("datime", datime)
    tree.Branch("WorkingPoint", wp_arr, "WorkingPoint/D")
    tree.Branch("Temperature", temp_arr, "Temperature/D")
    tree.Branch("TriggerRate", trate_arr, "TriggerRate/D")
    tree.Branch("TriggerMaskChannels", tm_channels)
    tree.Branch("TriggerMaskStrips", tm_strips)
    tree.Branch("TriggerMaskSize", tm_size)
    # cluster-index branches for 4th-plane tracks (declared in C++ but never filled)
    tree.Branch("TrackCluster_z4_index", tcl_z4_idx)
    tree.Branch("TrackCluster_y4_index", tcl_y4_idx)

    # ── fill slow-control scalars (constant across events) ───────────────────
    wp_arr[0] = float(sc_wp)
    temp_arr[0] = sc_temperature
    trate_arr[0] = sc_tr

    # ── event-level counters ─────────────────────────────────────────────────
    n_ev_with_3p = 0
    n_ev_with_4p = 0
    n_ev_with_3p_xz = 0
    n_ev_with_3p_xy = 0
    n_ev_x1 = 0; n_ev_x2 = 0; n_ev_x3 = 0; n_ev_x4 = 0
    n_ev_y1 = 0; n_ev_y2 = 0; n_ev_y3 = 0; n_ev_y4 = 0
    N_tr_xy_3p = 0; N_tr_xz_3p = 0; N_tr_3p = 0
    N_tr_xy_4p = 0; N_tr_xz_4p = 0; N_tr_4p = 0
    N_good_3p = 0; N_good_4p = 0
    ev = 0

    # ── main event loop ───────────────────────────────────────────────────────
    N_CHANNELS = 32
    try:
        adc_file = open(complete_adc_name)
    except FileNotFoundError:
        print(f"ERROR: cannot open ADC file {complete_adc_name}")
        sys.exit(1)

    for event_line in adc_file:
        ev += 1

        event_info = read_event(event_line, sorted_ch)
        all_boards_adc = event_info["boards"]

        # fill trigger mask branches
        _fill_vvd(tm_channels, event_info["TrMask_channels"])
        _fill_vvd(tm_strips, event_info["TrMask_strips"])
        _fill_vi(tm_size, event_info["TrMask_size"])

        # ── compute energy deposits ──────────────────────────────────────────
        dep_p1x1=[]; dep_p1x2=[]; dep_p2x1=[]; dep_p2x2=[]
        dep_p3x1=[]; dep_p3x2=[]; dep_p4x1=[]; dep_p4x2=[]
        dep_p1y1=[]; dep_p1y2=[]; dep_p2y1=[]; dep_p2y2=[]
        dep_p3y1=[]; dep_p3y2=[]; dep_p4y1=[]; dep_p4y2=[]

        texp_1x1=texp_1x2=texp_2x1=texp_2x2=0.0
        texp_3x1=texp_3x2=texp_4x1=texp_4x2=0.0
        texp_1y1=texp_1y2=texp_2y1=texp_2y2=0.0
        texp_3y1=texp_3y2=texp_4y1=texp_4y2=0.0

        for b in range(N_BOARDS):
            view_b = views[b] if b < len(views) else ""
            nst = n_stations[b] if b < len(n_stations) else 0
            adc_counts = all_boards_adc[b]
            peds_b = boards_peds[b]
            one_phe_b = boards_one_phes[b]
            t_exp_b = event_info["timeExp"][b]

            # time expansions
            if nst == 1:
                if view_b == "x1": texp_1x1 = t_exp_b
                elif view_b == "x2": texp_1x2 = t_exp_b
                elif view_b == "y1": texp_1y1 = t_exp_b
                elif view_b == "y2": texp_1y2 = t_exp_b
            elif nst == 2:
                if view_b == "x1": texp_2x1 = t_exp_b
                elif view_b == "x2": texp_2x2 = t_exp_b
                elif view_b == "y1": texp_2y1 = t_exp_b
                elif view_b == "y2": texp_2y2 = t_exp_b
            elif nst == 3:
                if view_b == "x1": texp_3x1 = t_exp_b
                elif view_b == "x2": texp_3x2 = t_exp_b
                elif view_b == "y1": texp_3y1 = t_exp_b
                elif view_b == "y2": texp_3y2 = t_exp_b
            elif nst == 4:
                if view_b == "x1": texp_4x1 = t_exp_b
                elif view_b == "x2": texp_4x2 = t_exp_b
                elif view_b == "y1": texp_4y1 = t_exp_b
                elif view_b == "y2": texp_4y2 = t_exp_b

            # deposits = (ADC - ped) / OnePhe
            deposits_b = [
                (adc_counts[ch] - peds_b[ch]) / one_phe_b[ch]
                for ch in range(N_CHANNELS)
            ]

            if nst == 1:
                if view_b == "x1": dep_p1x1 = deposits_b
                elif view_b == "x2": dep_p1x2 = deposits_b
                elif view_b == "y1": dep_p1y1 = deposits_b
                elif view_b == "y2": dep_p1y2 = deposits_b
            elif nst == 2:
                if view_b == "x1": dep_p2x1 = deposits_b
                elif view_b == "x2": dep_p2x2 = deposits_b
                elif view_b == "y1": dep_p2y1 = deposits_b
                elif view_b == "y2": dep_p2y2 = deposits_b
            elif nst == 3:
                if view_b == "x1": dep_p3x1 = deposits_b
                elif view_b == "x2": dep_p3x2 = deposits_b
                elif view_b == "y1": dep_p3y1 = deposits_b
                elif view_b == "y2": dep_p3y2 = deposits_b
            elif nst == 4:
                if view_b == "x1": dep_p4x1 = deposits_b
                elif view_b == "x2": dep_p4x2 = deposits_b
                elif view_b == "y1": dep_p4y1 = deposits_b
                elif view_b == "y2": dep_p4y2 = deposits_b

        # concatenate half-planes → 64 strips
        dep_p1x = dep_p1x1 + dep_p1x2
        dep_p2x = dep_p2x1 + dep_p2x2
        dep_p3x = dep_p3x1 + dep_p3x2
        dep_p4x = dep_p4x1 + dep_p4x2
        dep_p1y = dep_p1y2 + dep_p1y1   # y is reversed
        dep_p2y = dep_p2y2 + dep_p2y1
        dep_p3y = dep_p3y2 + dep_p3y1
        dep_p4y = dep_p4y2 + dep_p4y1

        # ── clustering ───────────────────────────────────────────────────────
        tm_s = event_info["TrMask_strips"]
        res_p1x = create_cluster_list(dep_p1x, s1, s2, s3, texp_1x1, texp_1x2,
                                      tm_s[0], tm_s[1])
        res_p2x = create_cluster_list(dep_p2x, s1, s2, s3, texp_2x1, texp_2x2,
                                      tm_s[4], tm_s[5])
        res_p3x = create_cluster_list(dep_p3x, s1, s2, s3, texp_3x1, texp_3x2,
                                      tm_s[8], tm_s[9])
        res_p4x = create_cluster_list(dep_p4x, s1, s2, s3, texp_4x1, texp_4x2,
                                      tm_s[12], tm_s[13])
        res_p1y = create_cluster_list(dep_p1y, s1, s2, s3, texp_1y2, texp_1y1,
                                      tm_s[3], tm_s[2])
        res_p2y = create_cluster_list(dep_p2y, s1, s2, s3, texp_2y2, texp_2y1,
                                      tm_s[7], tm_s[6])
        res_p3y = create_cluster_list(dep_p3y, s1, s2, s3, texp_3y2, texp_3y1,
                                      tm_s[11], tm_s[10])
        res_p4y = create_cluster_list(dep_p4y, s1, s2, s3, texp_4y2, texp_4y1,
                                      tm_s[15], tm_s[14])

        # ── fill cluster branches ─────────────────────────────────────────────
        _fill_vd(cl_texp_z1, res_p1x["TimeExpansions"])
        _fill_vd(cl_texp_z2, res_p2x["TimeExpansions"])
        _fill_vd(cl_texp_z3, res_p3x["TimeExpansions"])
        _fill_vd(cl_texp_z4, res_p4x["TimeExpansions"])
        _fill_vd(cl_texp_y1, res_p1y["TimeExpansions"])
        _fill_vd(cl_texp_y2, res_p2y["TimeExpansions"])
        _fill_vd(cl_texp_y3, res_p3y["TimeExpansions"])
        _fill_vd(cl_texp_y4, res_p4y["TimeExpansions"])

        ncl_z1[0] = len(res_p1x["ClustersEnergy"])
        ncl_z2[0] = len(res_p2x["ClustersEnergy"])
        ncl_z3[0] = len(res_p3x["ClustersEnergy"])
        ncl_z4[0] = len(res_p4x["ClustersEnergy"])
        ncl_y1[0] = len(res_p1y["ClustersEnergy"])
        ncl_y2[0] = len(res_p2y["ClustersEnergy"])
        ncl_y3[0] = len(res_p3y["ClustersEnergy"])
        ncl_y4[0] = len(res_p4y["ClustersEnergy"])

        if ncl_z1[0] > 0: n_ev_x1 += 1
        if ncl_z2[0] > 0: n_ev_x2 += 1
        if ncl_z3[0] > 0: n_ev_x3 += 1
        if ncl_z4[0] > 0: n_ev_x4 += 1
        if ncl_y1[0] > 0: n_ev_y1 += 1
        if ncl_y2[0] > 0: n_ev_y2 += 1
        if ncl_y3[0] > 0: n_ev_y3 += 1
        if ncl_y4[0] > 0: n_ev_y4 += 1

        for (vv, res, key) in [
            (cl_en_z1,  res_p1x, "ClustersEnergy"),
            (cl_pos_z1, res_p1x, "ClustersPositions"),
            (cl_size_z1,res_p1x, "ClustersSize"),
            (cl_en_z2,  res_p2x, "ClustersEnergy"),
            (cl_pos_z2, res_p2x, "ClustersPositions"),
            (cl_size_z2,res_p2x, "ClustersSize"),
            (cl_en_z3,  res_p3x, "ClustersEnergy"),
            (cl_pos_z3, res_p3x, "ClustersPositions"),
            (cl_size_z3,res_p3x, "ClustersSize"),
            (cl_en_z4,  res_p4x, "ClustersEnergy"),
            (cl_pos_z4, res_p4x, "ClustersPositions"),
            (cl_size_z4,res_p4x, "ClustersSize"),
            (cl_en_y1,  res_p1y, "ClustersEnergy"),
            (cl_pos_y1, res_p1y, "ClustersPositions"),
            (cl_size_y1,res_p1y, "ClustersSize"),
            (cl_en_y2,  res_p2y, "ClustersEnergy"),
            (cl_pos_y2, res_p2y, "ClustersPositions"),
            (cl_size_y2,res_p2y, "ClustersSize"),
            (cl_en_y3,  res_p3y, "ClustersEnergy"),
            (cl_pos_y3, res_p3y, "ClustersPositions"),
            (cl_size_y3,res_p3y, "ClustersSize"),
            (cl_en_y4,  res_p4y, "ClustersEnergy"),
            (cl_pos_y4, res_p4y, "ClustersPositions"),
            (cl_size_y4,res_p4y, "ClustersSize"),
        ]:
            if key == "ClustersSize":
                _fill_vi(vv, res[key])
            else:
                _fill_vd(vv, res[key])

        for (vv, res, key) in [
            (st_en_z1,  res_p1x, "StripsEnergy"),
            (st_pos_z1, res_p1x, "StripsPositions"),
            (st_id_z1,  res_p1x, "StripsID"),
            (st_en_z2,  res_p2x, "StripsEnergy"),
            (st_pos_z2, res_p2x, "StripsPositions"),
            (st_id_z2,  res_p2x, "StripsID"),
            (st_en_z3,  res_p3x, "StripsEnergy"),
            (st_pos_z3, res_p3x, "StripsPositions"),
            (st_id_z3,  res_p3x, "StripsID"),
            (st_en_z4,  res_p4x, "StripsEnergy"),
            (st_pos_z4, res_p4x, "StripsPositions"),
            (st_id_z4,  res_p4x, "StripsID"),
            (st_en_y1,  res_p1y, "StripsEnergy"),
            (st_pos_y1, res_p1y, "StripsPositions"),
            (st_id_y1,  res_p1y, "StripsID"),
            (st_en_y2,  res_p2y, "StripsEnergy"),
            (st_pos_y2, res_p2y, "StripsPositions"),
            (st_id_y2,  res_p2y, "StripsID"),
            (st_en_y3,  res_p3y, "StripsEnergy"),
            (st_pos_y3, res_p3y, "StripsPositions"),
            (st_id_y3,  res_p3y, "StripsID"),
            (st_en_y4,  res_p4y, "StripsEnergy"),
            (st_pos_y4, res_p4y, "StripsPositions"),
            (st_id_y4,  res_p4y, "StripsID"),
        ]:
            _fill_vvd(vv, res[key])

        # ── tracking ──────────────────────────────────────────────────────────
        cl_pos_z1_list = list(res_p1x["ClustersPositions"])
        cl_pos_z2_list = list(res_p2x["ClustersPositions"])
        cl_pos_z3_list = list(res_p3x["ClustersPositions"])
        cl_pos_z4_list = list(res_p4x["ClustersPositions"])
        cl_en_z1_list  = list(res_p1x["ClustersEnergy"])
        cl_en_z2_list  = list(res_p2x["ClustersEnergy"])
        cl_en_z3_list  = list(res_p3x["ClustersEnergy"])
        cl_en_z4_list  = list(res_p4x["ClustersEnergy"])
        cl_texp_z1_l   = list(res_p1x["TimeExpansions"])
        cl_texp_z2_l   = list(res_p2x["TimeExpansions"])
        cl_texp_z3_l   = list(res_p3x["TimeExpansions"])
        cl_texp_z4_l   = list(res_p4x["TimeExpansions"])

        cl_pos_y1_list = list(res_p1y["ClustersPositions"])
        cl_pos_y2_list = list(res_p2y["ClustersPositions"])
        cl_pos_y3_list = list(res_p3y["ClustersPositions"])
        cl_pos_y4_list = list(res_p4y["ClustersPositions"])
        cl_en_y1_list  = list(res_p1y["ClustersEnergy"])
        cl_en_y2_list  = list(res_p2y["ClustersEnergy"])
        cl_en_y3_list  = list(res_p3y["ClustersEnergy"])
        cl_en_y4_list  = list(res_p4y["ClustersEnergy"])
        cl_texp_y1_l   = list(res_p1y["TimeExpansions"])
        cl_texp_y2_l   = list(res_p2y["TimeExpansions"])
        cl_texp_y3_l   = list(res_p3y["TimeExpansions"])
        cl_texp_y4_l   = list(res_p4y["TimeExpansions"])

        tr_xz = make_tracks(
            cl_pos_z1_list, cl_pos_z2_list, cl_pos_z3_list, cl_pos_z4_list,
            cl_en_z1_list,  cl_en_z2_list,  cl_en_z3_list,  cl_en_z4_list,
            cl_texp_z1_l,   cl_texp_z2_l,   cl_texp_z3_l,   cl_texp_z4_l,
            prox_xz, x_pos, z_add, sigma_z,
        )
        tr_xy = make_tracks(
            cl_pos_y1_list, cl_pos_y2_list, cl_pos_y3_list, cl_pos_y4_list,
            cl_en_y1_list,  cl_en_y2_list,  cl_en_y3_list,  cl_en_y4_list,
            cl_texp_y1_l,   cl_texp_y2_l,   cl_texp_y3_l,   cl_texp_y4_l,
            prox_xy, x_pos, y_add, sigma_y,
        )

        # fill 3p track branches
        _fill_vd(int_3p_xz, tr_xz["intercepts_3p"])
        _fill_vd(slp_3p_xz, tr_xz["slopes_3p"])
        _fill_vd(chi_3p_xz, tr_xz["chiSquares_3p"])
        _fill_vd(int_3p_xy, tr_xy["intercepts_3p"])
        _fill_vd(slp_3p_xy, tr_xy["slopes_3p"])
        _fill_vd(chi_3p_xy, tr_xy["chiSquares_3p"])

        ntr3p_xz[0] = len(tr_xz["intercepts_3p"])
        ntr3p_xy[0] = len(tr_xy["intercepts_3p"])

        _fill_vi(tcl_z1_idx, tr_xz["cluster_index_1"])
        _fill_vi(tcl_z2_idx, tr_xz["cluster_index_2"])
        _fill_vi(tcl_z3_idx, tr_xz["cluster_index_3"])
        _fill_vi(tcl_y1_idx, tr_xy["cluster_index_1"])
        _fill_vi(tcl_y2_idx, tr_xy["cluster_index_2"])
        _fill_vi(tcl_y3_idx, tr_xy["cluster_index_3"])

        _fill_vd(res_3p_z1, tr_xz["residue_c1"])
        _fill_vd(res_3p_z2, tr_xz["residue_c2"])
        _fill_vd(res_3p_z3, tr_xz["residue_c3"])
        _fill_vd(res_3p_y1, tr_xy["residue_c1"])
        _fill_vd(res_3p_y2, tr_xy["residue_c2"])
        _fill_vd(res_3p_y3, tr_xy["residue_c3"])

        _fill_vd(en_3p_xz, tr_xz["TrackEnergy_3p"])
        _fill_vd(en_3p_xy, tr_xy["TrackEnergy_3p"])

        _fill_vi(plane4_xz, tr_xz["Plane4th_isIntercepted"])
        _fill_vi(plane4_xy, tr_xy["Plane4th_isIntercepted"])
        _fill_vd(exp_p4_xz, tr_xz["ExpectedPosition_OnPlane4th"])
        _fill_vd(exp_p4_xy, tr_xy["ExpectedPosition_OnPlane4th"])

        best_chi_xy_arr[0]  = tr_xy["BestChi"]
        best_en_xy_arr[0]   = tr_xy["BestEnergy"]
        best_chi_xz_arr[0]  = tr_xz["BestChi"]
        best_en_xz_arr[0]   = tr_xz["BestEnergy"]
        best_chi_xy_idx[0]  = tr_xy["BestChi_index"]
        best_en_xy_idx[0]   = tr_xy["BestEnergy_index"]
        best_chi_xz_idx[0]  = tr_xz["BestChi_index"]
        best_en_xz_idx[0]   = tr_xz["BestEnergy_index"]

        N_tr_xy_3p += ntr3p_xy[0]
        N_tr_xz_3p += ntr3p_xz[0]
        N_tr_3p += ntr3p_xy[0] * ntr3p_xz[0]

        # cluster-is-in-track
        _fill_vi(is_in3p_z1, tr_xz["IsInTrack_clusters1"])
        _fill_vi(is_in3p_z2, tr_xz["IsInTrack_clusters2"])
        _fill_vi(is_in3p_z3, tr_xz["IsInTrack_clusters3"])
        _fill_vi(is_in3p_y1, tr_xy["IsInTrack_clusters1"])
        _fill_vi(is_in3p_y2, tr_xy["IsInTrack_clusters2"])
        _fill_vi(is_in3p_y3, tr_xy["IsInTrack_clusters3"])
        _fill_vi(is_in4p_z1, tr_xz["IsInTrack_clusters1_4p"])
        _fill_vi(is_in4p_z2, tr_xz["IsInTrack_clusters2_4p"])
        _fill_vi(is_in4p_z3, tr_xz["IsInTrack_clusters3_4p"])
        _fill_vi(is_in4p_y1, tr_xy["IsInTrack_clusters1_4p"])
        _fill_vi(is_in4p_y2, tr_xy["IsInTrack_clusters2_4p"])
        _fill_vi(is_in4p_y3, tr_xy["IsInTrack_clusters3_4p"])

        # 4p tracking branches
        _fill_vvd(p4_slp_xz, tr_xz["slope_4p"])
        _fill_vvd(p4_chi_xz, tr_xz["chiSquares_4p"])
        _fill_vvd(disp_xz,   tr_xz["displacement_p4"])
        _fill_vvd(cl4_idx_xz,tr_xz["cluster_indices_4"])
        _fill_vvd(scat_xz,   tr_xz["ScatteringAngles"])

        _fill_vvd(p4_int_xy, tr_xy["intercept_4p"])
        _fill_vvd(p4_slp_xy, tr_xy["slope_4p"])
        _fill_vvd(p4_chi_xy, tr_xy["chiSquares_4p"])
        _fill_vvd(disp_xy,   tr_xy["displacement_p4"])
        _fill_vvd(cl4_idx_xy,tr_xy["cluster_indices_4"])
        _fill_vvd(scat_xy,   tr_xy["ScatteringAngles"])

        # 3D best track
        best_xy_ind = tr_xy["BestChi_index"]
        best_xz_ind = tr_xz["BestChi_index"]
        if tr_xy["BestChi_index"] == tr_xy["BestEnergy_index"]:
            best_xy_ind = tr_xy["BestEnergy_index"]
        if tr_xz["BestChi_index"] == tr_xz["BestEnergy_index"]:
            best_xz_ind = tr_xz["BestEnergy_index"]

        if ntr3p_xz[0] > 0 and ntr3p_xy[0] > 0:
            isbt3p_xz.clear()
            isbt3p_xy.clear()
            if best_xz_ind >= 0 and best_xy_ind >= 0:
                coords_3p = track_angular_coordinates(
                    tr_xy["slopes_3p"][best_xy_ind],
                    tr_xz["slopes_3p"][best_xz_ind],
                    x_pos[0], x_pos[2],
                )
                theta_3p_arr[0] = coords_3p[0]
                phi_3p_arr[0]   = coords_3p[1]
                N_good_3p += 1
                bt3p_xy_idx[0] = best_xy_ind
                bt3p_xz_idx[0] = best_xz_ind
                bt3p_chi_xy[0] = tr_xy["chiSquares_3p"][best_xy_ind]
                bt3p_chi_xz[0] = tr_xz["chiSquares_3p"][best_xz_ind]
                for t in range(ntr3p_xz[0]):
                    isbt3p_xz.push_back(1 if t == best_xz_ind else 0)
                for t in range(ntr3p_xy[0]):
                    isbt3p_xy.push_back(1 if t == best_xy_ind else 0)
            else:
                for _ in range(ntr3p_xz[0]):
                    isbt3p_xz.push_back(0)
                for _ in range(ntr3p_xy[0]):
                    isbt3p_xy.push_back(0)
                bt3p_chi_xy[0] = -1.0; bt3p_chi_xz[0] = -1.0
                bt3p_xy_idx[0] = -1;   bt3p_xz_idx[0] = -1
                theta_3p_arr[0] = -1.0; phi_3p_arr[0] = -1.0
        else:
            isbt3p_xz.clear(); isbt3p_xy.clear()
            bt3p_chi_xy[0] = -1.0; bt3p_chi_xz[0] = -1.0
            bt3p_xy_idx[0] = -1;   bt3p_xz_idx[0] = -1
            theta_3p_arr[0] = -1.0; phi_3p_arr[0] = -1.0

        # 4p best track
        t3p2_4p_xz = tr_xz["Track_3p_to_4p_index"]
        t3p2_4p_xy = tr_xy["Track_3p_to_4p_index"]
        if t3p2_4p_xz and t3p2_4p_xy:
            try:
                idx4_xz = t3p2_4p_xz.index(best_xz_ind)
            except ValueError:
                idx4_xz = -1
            try:
                idx4_xy = t3p2_4p_xy.index(best_xy_ind)
            except ValueError:
                idx4_xy = -1

            if idx4_xz >= 0 and idx4_xy >= 0:
                t3p_of_4p_xy[0] = idx4_xy
                t3p_of_4p_xz[0] = idx4_xz

                # pick 4p track with Texp > 0
                bt4p_idx_xy = 0
                isnull_xy = 1
                clt_xy = tr_xy["cluster_indices_4"][idx4_xy]
                int4_xy = tr_xy["intercept_4p"][idx4_xy]
                for k in range(len(int4_xy)):
                    cidx = int(clt_xy[k]) if clt_xy else 0
                    texp_val = cl_texp_y4_l[cidx] if cidx < len(cl_texp_y4_l) else 0.0
                    if texp_val > 0:
                        isnull_xy = 0
                        bt4p_idx_xy = k
                        break
                bt4p_texp_null_xy[0] = isnull_xy
                t4p_idx_xy[0] = bt4p_idx_xy

                bt4p_idx_xz = 0
                isnull_xz = 1
                clt_xz = tr_xz["cluster_indices_4"][idx4_xz]
                int4_xz = tr_xz["intercept_4p"][idx4_xz]
                for k in range(len(int4_xz)):
                    cidx = int(clt_xz[k]) if clt_xz else 0
                    texp_val = cl_texp_z4_l[cidx] if cidx < len(cl_texp_z4_l) else 0.0
                    if texp_val > 0:
                        isnull_xz = 0
                        bt4p_idx_xz = k
                        break
                bt4p_texp_null_xz[0] = isnull_xz
                t4p_idx_xz[0] = bt4p_idx_xz

                bt4p_chi_xy[0] = tr_xy["chiSquares_4p"][idx4_xy][bt4p_idx_xy]
                bt4p_chi_xz[0] = tr_xz["chiSquares_4p"][idx4_xz][bt4p_idx_xz]
                bts_scat_xy[0] = tr_xy["ScatteringAngles"][idx4_xy][bt4p_idx_xy]
                bts_scat_xz[0] = tr_xz["ScatteringAngles"][idx4_xz][bt4p_idx_xz]

                coords_4p = track_angular_coordinates(
                    tr_xy["slope_4p"][idx4_xy][bt4p_idx_xy],
                    tr_xz["slope_4p"][idx4_xz][bt4p_idx_xz],
                    x_pos[0], x_pos[3],
                )
                theta_4p_arr[0] = coords_4p[0]
                phi_4p_arr[0]   = coords_4p[1]
                N_good_4p += 1
            else:
                _reset_4p_scalars(bt4p_chi_xy, bt4p_chi_xz, bts_scat_xy, bts_scat_xz,
                                  bt4p_texp_null_xz, bt4p_texp_null_xy,
                                  t4p_idx_xz, t4p_idx_xy, t3p_of_4p_xy, t3p_of_4p_xz,
                                  theta_4p_arr, phi_4p_arr)
        else:
            _reset_4p_scalars(bt4p_chi_xy, bt4p_chi_xz, bts_scat_xy, bts_scat_xz,
                              bt4p_texp_null_xz, bt4p_texp_null_xy,
                              t4p_idx_xz, t4p_idx_xy, t3p_of_4p_xy, t3p_of_4p_xz,
                              theta_4p_arr, phi_4p_arr)

        # event counters
        n4p_xy = sum(1 for n in tr_xy["Ntracks_4p"] if n > 0)
        n4p_xz = sum(1 for n in tr_xz["Ntracks_4p"] if n > 0)
        if ntr3p_xz[0] > 0 and ntr3p_xy[0] > 0:
            n_ev_with_3p += 1
        if ntr3p_xz[0] > 0: n_ev_with_3p_xz += 1
        if ntr3p_xy[0] > 0: n_ev_with_3p_xy += 1
        if n4p_xz > 0 and n4p_xy > 0:
            n_ev_with_4p += 1
            N_tr_xy_4p += n4p_xy
            N_tr_xz_4p += n4p_xz
            N_tr_4p += n4p_xz * n4p_xy

        tree.Fill()

    adc_file.close()

    # ── print summary ─────────────────────────────────────────────────────────
    print(f"N events with at least a 3p track: {n_ev_with_3p}")
    print(f"N events with at least a 4p track: {n_ev_with_4p}")
    print(f"N events with at least a 3p track on the plane xy: {n_ev_with_3p_xy}")
    print(f"N events with at least a 3p track on the plane xz: {n_ev_with_3p_xz}")
    print(f"Events with at least 1 cluster in Z1: {n_ev_x1}")
    print(f"Events with at least 1 cluster in Z2: {n_ev_x2}")
    print(f"Events with at least 1 cluster in Z3: {n_ev_x3}")
    print(f"Events with at least 1 cluster in Z4: {n_ev_x4}")
    print(f"Events with at least 1 cluster in Y1: {n_ev_y1}")
    print(f"Events with at least 1 cluster in Y2: {n_ev_y2}")
    print(f"Events with at least 1 cluster in Y3: {n_ev_y3}")
    print(f"Events with at least 1 cluster in Y4: {n_ev_y4}")

    # ── add post-loop constant branches ──────────────────────────────────────
    run_dur_arr = array("d", [0.0])   # RunDuration not computed (commented in C++)
    nevents_arr = array("i", [ev])
    b_run_dur = tree.Branch("RunDuration", run_dur_arr, "RunDuration/D")
    b_nevents = tree.Branch("Nevents", nevents_arr, "Nevents/I")
    for _ in range(ev):
        b_run_dur.Fill()
        b_nevents.Fill()

    # ── cluster energy histograms (for mini-tree statistics) ─────────────────
    def _tree_mean_rms(branch_name):
        h = ROOT.TH1F(f"h_{branch_name}", "", 1000, 0, 1000)
        tree.Draw(f"{branch_name}>>h_{branch_name}", "", "goff")
        mean = h.GetMean()
        rms = h.GetRMS()
        h.Delete()
        return mean, rms

    def _ncl_mean_rms(branch_name):
        h = ROOT.TH1F(f"hN_{branch_name}", "", 10, 0, 10)
        tree.Draw(f"{branch_name}>>hN_{branch_name}", "", "goff")
        mean = h.GetMean()
        rms = h.GetRMS()
        h.Delete()
        return mean, rms

    en_stats = {k: _tree_mean_rms(k) for k in (
        "ClusterEnergy_Z1", "ClusterEnergy_Z2", "ClusterEnergy_Z3", "ClusterEnergy_Z4",
        "ClusterEnergy_Y1", "ClusterEnergy_Y2", "ClusterEnergy_Y3", "ClusterEnergy_Y4",
    )}
    ncl_stats = {k: _ncl_mean_rms(k) for k in (
        "Nclusters_Z1", "Nclusters_Z2", "Nclusters_Z3", "Nclusters_Z4",
        "Nclusters_Y1", "Nclusters_Y2", "Nclusters_Y3", "Nclusters_Y4",
    )}

    tree.Write()
    file_root.Close()

    # ── mini-tree ─────────────────────────────────────────────────────────────
    file_mini = ROOT.TFile(mini_tree_name, "recreate")
    tree_info = ROOT.TTree("Run_info", "A tree containing some run general info")

    mi_ev     = array("i", [ev])
    mi_run    = array("i", [run])
    mi_wp     = array("d", [float(sc_wp)])
    mi_temp   = array("d", [sc_temperature])
    mi_tr     = array("d", [sc_tr])
    mi_n3p    = array("d", [float(n_ev_with_3p)])
    mi_n3pxy  = array("d", [float(n_ev_with_3p_xy)])
    mi_n3pxz  = array("d", [float(n_ev_with_3p_xz)])
    mi_n4p    = array("d", [float(n_ev_with_4p)])
    mi_ntr3xy = array("d", [float(N_tr_xy_3p)])
    mi_ntr3xz = array("d", [float(N_tr_xz_3p)])
    mi_ntr3   = array("d", [float(N_tr_3p)])
    mi_ntr4xy = array("d", [float(N_tr_xy_4p)])
    mi_ntr4xz = array("d", [float(N_tr_xz_4p)])
    mi_ntr4   = array("d", [float(N_tr_4p)])
    mi_ncl_x1 = array("d", [float(n_ev_x1)])
    mi_ncl_x2 = array("d", [float(n_ev_x2)])
    mi_ncl_x3 = array("d", [float(n_ev_x3)])
    mi_ncl_x4 = array("d", [float(n_ev_x4)])
    mi_ncl_y1 = array("d", [float(n_ev_y1)])
    mi_ncl_y2 = array("d", [float(n_ev_y2)])
    mi_ncl_y3 = array("d", [float(n_ev_y3)])
    mi_ncl_y4 = array("d", [float(n_ev_y4)])
    mi_s1     = array("d", [s1])
    mi_s2     = array("d", [s2])
    mi_s3     = array("d", [s3])
    mi_pxz    = array("d", [prox_xz])
    mi_pxy    = array("d", [prox_xy])
    mi_rdur   = array("d", [0.0])
    mi_ng3    = array("i", [N_good_3p])
    mi_ng4    = array("i", [N_good_4p])

    # boards_OnePhes as vector<vector<double>>
    boph_vvd = _vvd()
    _fill_vvd(boph_vvd, boards_one_phes)
    # boards_Is1phe_copy as vector<vector<double>>
    bic_vvd = _vvd()
    _fill_vvd(bic_vvd, boards_is1phe_copy)

    tree_info.Branch("Nevents", mi_ev, "Nevents/I")
    tree_info.Branch("Run", mi_run, "Run/I")
    tree_info.Branch("boards_OnePhes", boph_vvd)
    tree_info.Branch("WorkingPoint", mi_wp, "WorkingPoint/D")
    tree_info.Branch("Temperature", mi_temp, "Temperature/D")
    tree_info.Branch("TriggerRate", mi_tr, "TriggerRate/D")
    tree_info.Branch("Nev_withAtrack3p", mi_n3p, "Nev_withAtrack3p/D")
    tree_info.Branch("Nev_withAtrack3p_xy", mi_n3pxy, "Nev_withAtrack3p_xy/D")
    tree_info.Branch("Nev_withAtrack3p_xz", mi_n3pxz, "Nev_withAtrack3p_xz/D")
    tree_info.Branch("Nev_withAtrack4p", mi_n4p, "Nev_withAtrack4p/D")
    tree_info.Branch("Ntracks_xy_3p", mi_ntr3xy, "Ntracks_xy_3p/D")
    tree_info.Branch("Ntracks_xz_3p", mi_ntr3xz, "Ntracks_xz_3p/D")
    tree_info.Branch("Ntracks_3p", mi_ntr3, "Ntracks_3p/D")
    tree_info.Branch("Ntracks_xy_4p", mi_ntr4xy, "Ntracks_xy_4p/D")
    tree_info.Branch("Ntracks_xz_4p", mi_ntr4xz, "Ntracks_xz_4p/D")
    tree_info.Branch("Ntracks_4p", mi_ntr4, "Ntracks_4p/D")
    tree_info.Branch("Nev_withAcluster_Z1", mi_ncl_x1, "Nev_withAcluster_Z1/D")
    tree_info.Branch("Nev_withAcluster_Z2", mi_ncl_x2, "Nev_withAcluster_Z2/D")
    tree_info.Branch("Nev_withAcluster_Z3", mi_ncl_x3, "Nev_withAcluster_Z3/D")
    tree_info.Branch("Nev_withAcluster_Z4", mi_ncl_x4, "Nev_withAcluster_Z4/D")
    tree_info.Branch("Nev_withAcluster_Y1", mi_ncl_y1, "Nev_withAcluster_Y1/D")
    tree_info.Branch("Nev_withAcluster_Y2", mi_ncl_y2, "Nev_withAcluster_Y2/D")
    tree_info.Branch("Nev_withAcluster_Y3", mi_ncl_y3, "Nev_withAcluster_Y3/D")
    tree_info.Branch("Nev_withAcluster_Y4", mi_ncl_y4, "Nev_withAcluster_Y4/D")
    tree_info.Branch("EnergyCut_clusterStrip", mi_s1, "EnergyCut_clusterStrip/D")
    tree_info.Branch("EnergyCut_singleStrip",  mi_s2, "EnergyCut_singleStrip/D")
    tree_info.Branch("EnergyCut_additionalStrip", mi_s3, "EnergyCut_additionalStrip/D")
    tree_info.Branch("proximity_cut_xz", mi_pxz, "proximity_cut_xz/D")
    tree_info.Branch("proximity_cut_xy", mi_pxy, "proximity_cut_xy/D")
    tree_info.Branch("RunDuration", mi_rdur, "RunDuration/D")

    # Keep references alive so ROOT does not read freed memory.
    _mi_extra_arrs = []

    def _mi_d_branch(name, val):
        a = array("d", [val])
        _mi_extra_arrs.append(a)
        tree_info.Branch(name, a, f"{name}/D")

    for en_branch, (mean_val, rms_val) in en_stats.items():
        suffix = en_branch.replace("ClusterEnergy_", "")
        _mi_d_branch(f"Mean_clusterEnergy_{suffix}", mean_val)
        _mi_d_branch(f"RMS_clusterEnergy_{suffix}", rms_val)
    for ncl_branch, (mean_val, rms_val) in ncl_stats.items():
        suffix = ncl_branch.replace("Nclusters_", "")
        _mi_d_branch(f"Mean_Nclusters_{suffix}", mean_val)
        _mi_d_branch(f"RMS_Nclusters_{suffix}", rms_val)

    tree_info.Branch("datime", datime)
    tree_info.Branch("IsOnePhe_aCopy", bic_vvd)
    tree_info.Branch("NGoodTracks3p", mi_ng3, "NGoodTracks3p/I")
    tree_info.Branch("NGoodTracks4p", mi_ng4, "NGoodTracks4p/I")

    tree_info.Fill()
    tree_info.Write()
    file_mini.Close()

    elapsed = time.time() - t_start
    print(f"Number of events: {ev}")
    print(f"RUN {run} COMPLETED. Find your data in ---> {root_file_name}")
    print(f"Find your  minitree in ---> {mini_tree_name}")


def _reset_4p_scalars(bt4p_chi_xy, bt4p_chi_xz, bts_scat_xy, bts_scat_xz,
                      bt4p_texp_null_xz, bt4p_texp_null_xy,
                      t4p_idx_xz, t4p_idx_xy, t3p_of_4p_xy, t3p_of_4p_xz,
                      theta_4p_arr, phi_4p_arr):
    bt4p_chi_xy[0] = -1.0; bt4p_chi_xz[0] = -1.0
    bts_scat_xy[0] = -1.0; bts_scat_xz[0] = -1.0
    bt4p_texp_null_xz[0] = -1; bt4p_texp_null_xy[0] = -1
    t4p_idx_xz[0] = -1;   t4p_idx_xy[0] = -1
    t3p_of_4p_xy[0] = -1; t3p_of_4p_xz[0] = -1
    theta_4p_arr[0] = -1.0; phi_4p_arr[0] = -1.0


if __name__ == "__main__":
    main()
