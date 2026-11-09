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
| `shared/reco_parameters.json` | `detector_geometry`, `reconstruction`, `strips`, `cluster_lists`, `tracking` |
| `data/data_parameters.json` | `electronics`, `raw_files`, `read_event`, `pedestals`, `slow_control`, `data_runtime` |

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
