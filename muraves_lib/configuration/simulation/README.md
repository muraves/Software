# Simulation-only configuration

Configuration used only by the simulation chain (`muraves/simulation/`).

- `simulation_parameters.json`: loaded on top of `../shared/reco_parameters.json` by
  `get_reco_config(chain="simulation")`, and may not redefine the shared sections
  (see `../README.md`). Holds the digitization settings: for now, which NPE/cm
  calibration the path-length digitizer uses by default.
- `npecm_per_run_v1.json`: the per-run, per-plane NPE/cm calibration from good data
  runs (Landau location parameter of path-length-corrected size-1 cluster energy).
  Used by `muraves-simCluster --pe-per-cm-file` (without a path) with `--detector`.

## How `npecm_per_run_v1.json` was made

The table holds, per detector and good run, the NPE/cm of each plane
(Y1–Y4, Z1–Z4), with the run's working point (`wp`) and setting (`set`:
same working point and same DAC10 table). Its own `info` block says what
the numbers are. It was produced by a student with the NPE conversion
benchmark in the simulation repository,
[muraves/Simulation_Studies](https://github.com/muraves/Simulation_Studies):

1. **Run selection.** Good runs only, chosen with `select_runs.py`.
   Runs are grouped in batches of 50 with the same setting
   (working point and DAC10 table), one batch per temperature period,
   and every run gets its batch's values; that is why neighbouring runs
   have identical numbers.
2. **Track selection** (`1_select_4p_tracks.C`), on reconstructed data:
   events whose best three-plane track passes a χ² cut (`chi2cutmax`)
   and has a matching four-plane track; per plane, the cluster energy
   corrected for the track's path length in the bar (`corrEnergy`).
3. **Landau fit** (`2_landau_fit.C`), per plane, in a fit window per
   plane (set by hand, or around the peak with `landau.auto_range`).
   As the file's `info` block says, the NPE/cm is the Landau location
   parameter (MPV) of the path-length-corrected energy of size-1
   clusters, divided by 1.7 cm.
4. **Validity.** A plane whose fit failed, or whose value is outside
   [5, 15] NPE/cm, is stored as `null`.

The benchmark's stages 3 and 4 (`3_merge_sim_add_uid.C`,
`4_add_energy_npe.C`) apply the calibration to simulated events in ROOT.
In this chain `muraves-simCluster --pe-per-cm-file` does that instead,
and does not use their output.

To be completed (asked to the student):

- the commit of `Simulation_Studies` and the folder of the benchmark;
- the criteria of `select_runs.py`;
- the reconstructed data version the fits used;
- the χ² cut and fit-window settings (`config.cfg`) used for v1;
- the script that ran stages 1–2 per batch and wrote the JSON.

A v2 table is made the same way, added next to v1, and selected by
changing `pe_per_cm_file` in `simulation_parameters.json`.

The detector geometry the simulation reconstructs with is not here: it is the
detector's entry in `../shared/reco_parameters.json` (`detector_geometry`), the same
the data chain uses. Values needed by both chains belong in `../shared/`.
