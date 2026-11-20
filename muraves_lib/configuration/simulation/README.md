# Simulation-only configuration

Configuration used only by the simulation chain (`muraves/simulation/`).

- `simulation_parameters.json`: loaded on top of `../shared/reco_parameters.json` by
  `get_reco_config(chain="simulation")`, and may not redefine the shared sections
  (see `../README.md`). Holds the digitization settings: for now, which NPE/cm
  calibration the path-length digitizer uses by default.
- `npecm_per_run_v1.json`: the per-run, per-plane NPE/cm calibration from good data
  runs (Landau location parameter of path-length-corrected size-1 cluster energy).
  Used by `muraves-simCluster --pe-per-cm-file` (without a path) with `--detector`.

The detector geometry the simulation reconstructs with is not here: it is the
detector's entry in `../shared/reco_parameters.json` (`detector_geometry`), the same
the data chain uses. Values needed by both chains belong in `../shared/`.
