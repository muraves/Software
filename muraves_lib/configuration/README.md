# MURAVES configuration

All detector and reconstruction configuration files, shipped with `muraves_lib` so that
every workflow (data and simulation) reads the same values. Files are split by the
chain that uses them:

```
configuration/
├── shared/       used by both the data and the simulation chains
├── data/         used only by the data chain (muraves/tracks_reconstruction)
└── simulation/   used only by the simulation chain (empty for now)
```

Workflow *run* settings (input/output paths, batch size, threads, cluster profile) are
not here: they stay next to each workflow, e.g. `muraves/tracks_reconstruction/config.yaml`.

## Reconstruction parameters (JSON)

| File | Sections |
|---|---|
| `shared/reco_parameters.json` | `detector_geometry`, `reconstruction`, `strips`, `cluster_lists`, `tracking`, `depth_correction` |
| `data/data_parameters.json` | `electronics`, `raw_files`, `read_event`, `pedestals`, `slow_control`, `data_runtime`, `depth_face_orientation` |

They are loaded with `muraves_lib.reco.reco_config.get_reco_config(chain=...)`, which
merges, in order:

1. `shared/reco_parameters.json`;
2. the file of the chain (`chain="data"` → `data/data_parameters.json`;
   `chain="simulation"` → `simulation/simulation_parameters.json`, once it exists);
3. an optional base file (`--base-config`);
4. an optional override file (`--config`, or `reco_override_file` in the workflow's `config.yaml`).

Every parameter is defined in exactly one file: a chain file that redefines a section of
the shared file is refused. Base and override files may only contain keys that already
exist in 1 + 2, so a misspelled or misplaced key stops the job instead of being ignored.
JSON has no comments: keys starting with `_` (`_about`, `_note`) are documentation and
are ignored by the code.

## `depth_correction` (shared) and `depth_face_orientation` (per chain)

Method B for 2-bar clusters ("depth correction"). The bars are triangles with alternating
orientation, so a cluster of two adjacent strips measures where the muon crosses the face
shared by the two bars: a 2D point at the depth `Xc` inside the plane, not a point at the
plane centre. With this correction the track fit places each 2-bar cluster at
`x_pos + Xc`; clusters of any other size stay at the plane centre. `Xc` comes from the
cluster position and the bar geometry only (`muraves_lib/reco/depth.py`):

```
k      = floor((z_c - first_strip_pos) / pitch)     # lower strip of the pair
B      = first_strip_pos + (k + 1/2) * pitch        # shared face at the plane centre
sign_k = +1 if k is even else -1
Xc     = -face_orientation * sign_k * h_over_p * (z_c - B)      # |Xc| <= h/2
```

Both chains compute the depths with `muraves_lib.reco.depth.plane_depths(cfg, hodoscope,
view, positions, sizes)`, which reads the parameters below.

`depth_correction` is in `shared/reco_parameters.json`, so data and simulation always have
the same switch and the same h/p:

- `enabled`: `true` (since 2026-11-26). `false` gives exactly the reconstruction without
  depths. When `true`, every track quantity (P2 candidate cut, 3p/4p fits, residues, P4
  displacement, scattering angle) uses the depths, and the depth used for each cluster is
  written in the `ClusterDepth_{Z,Y}{1..4}` branches [m] (always written, 0 when not applied).
  If the correction is enabled and `MakeTracks` is called without depths (a chain not yet
  connected, e.g. the simulation until
  [#32](https://github.com/muraves/Software/issues/32)), the tracks are fitted at the plane
  centre and a warning is logged once per process.
- `h_over_p`: bar height / strip pitch, the nominal geometric value 1/0.97. The data prefer a
  smaller value (about 0.7, MC about 0.85), to be studied before changing it.

`depth_face_orientation` is in each chain file, because the face orientation differs between
the real detector and the simulation (the data Y view is mirrored). Per hodoscope and view:
`+1` when an (even, odd) strip pair shares a "\" face (dz/dx ≈ −0.97), as in the simulated
geometry; `−1` when mirrored; `null` when not measured, so that hodoscope/view gets no
depth. With the correction enabled, a chain that calls `plane_depths` without this section,
or without its hodoscope, stops with an error. It is measured from the parity of the lower
strip of the 2-bar clusters of steep tracks: at slope ≥ +0.8, an even lower strip dominates
for `+1`, an odd one for `−1`.

- Data (`data/data_parameters.json`; v1, NERO, BLU and ROSSO, all four planes): Z +1, Y −1
  (93–96 % dominance).
- Simulation (Geant4 geometry): +1 in both views; the section is added when the simulation
  chain passes the depths to `MakeTracks` (#32).

**Residuals in v2 are taken at the cluster depth.** The `Residue_Track{3p,4p}_*` branches
are computed at `x_pos + ClusterDepth_*`, while the cluster positions (`ClusterPosition_*`,
`position_c*` of `MakeTracks`) still store only the coordinate along the plane (z or y). To
recompute a residual offline as `pos − (q + m·x)`, use `x = x_pos + ClusterDepth_*` of that
cluster, not the plane centre `x_pos`.

Validation (2026-11, h/p = 1/0.97): on 99 NERO good runs the P2 residual σ68 of the best 3p
track at |slope| 0.8–1.2 goes from 5.07 to 4.60 mm (Z) and from 5.33 to 4.54 mm (Y), and the
χ² < 2 fraction from 0.632 to 0.675 (Z) and from 0.554 to 0.625 (Y); in MC the slope error
vs truth goes from 14.0 to 12.7 mrad. In data the Y view gets slightly worse at |slope_xy|
0.6–0.8 and above 1.5. The number of 3p tracks changes by about −0.15 %.

## Data-only files

### `data/electronics_mapping/`

How the readout electronics are wired. Used by the reconstruction to turn raw ADC
values into strips on planes.

- `spiroc-hybrid-map.cfg`: for each strip (`STRIP`, 1–32), the SPIROC channel
  (`CANALI`) that reads it. The raw files store channels in electronics order; the
  reconstruction reorders them into strip order with this map.
- `telescope{ROSSO,NERO,BLU}.cfg`: one row per board. `n_scheda` is the board number in
  the raw file, `n_station` the station (1–4) and `type` the view (`x1`, `x2`, `y1`, `y2`).
  The reconstruction reads `n_station` and `type`, by column position; `n_mod` and
  `n_plane` are kept as readable identifiers. The plane positions are not here but in
  `detector_geometry` of `shared/reco_parameters.json`.

### `data/pedestal_1phe_values/`

Reference pedestal and 1-phe values per telescope and board (`ped_onephe_sk*.txt`),
from which the `2_PedAna` step builds the calibration files. See the README in that
folder for their origin.
