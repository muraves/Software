# Simulation-only configuration

`simulation_parameters.json` holds the parameters used only by the simulation chain: it is
loaded on top of `../shared/reco_parameters.json` by `get_reco_config(chain="simulation")`,
and may not redefine the shared sections (see `../README.md`). Values needed by both chains
belong in `../shared/` instead.

Sections: `depth_correction` (method B for 2-bar clusters, see `../README.md`).
