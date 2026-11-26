# Simulation-only configuration

Placeholder for the configuration used only by the simulation chain.

Parameters go in `simulation_parameters.json` in this folder: it is loaded on top of
`../shared/reco_parameters.json` by `get_reco_config(chain="simulation")`, and may not
redefine the shared sections (see `../README.md`). Values needed by both chains belong
in `../shared/` instead.
