# Tracks Reconstruction Pipeline (Snakemake)

This folder contains the MURAVES tracks reconstruction workflow orchestrated by Snakemake.

The main entrypoint is:

- `Snakefile`

The workflow runs the following stages:

1. Parse raw files (`1_Parser`)
2. Build the telescope pedestal/1phe files from the benchmark calibration files (`2_PedAna/PedestalReader.py`)
3. Run main reconstruction (`3_MainRecSof`)
4. Golden selection (`4_GoldenSelection`): keep only the events with a valid 3-plane **and** 4-plane track and write, per run, a flat `Tracks4ptree` (`Track4p_run<N>.root`) ready for physics analysis

### Shared reconstruction core (`muraves_lib.reco`)

The reconstruction algorithms that must be identical for data and simulation live in the
`muraves_lib` package, not in this folder:

| Module | Content |
|---|---|
| `muraves_lib/reco/cluster_lists.py` | strip clustering (`CreateClusterList`) |
| `muraves_lib/reco/tracking.py` | 3-plane / 4-plane track building (`MakeTracks`) |
| `muraves_lib/reco/angular_coordinates.py` | track angles (`TrackAngularCoordinates`) |
| `muraves_lib/reco/golden_selector.py` | golden-track definition (`is_golden`) |
| `muraves_lib/reco/reco_config.py` | configuration loader |
| `muraves_lib/configuration/` | all configuration files: `shared/` (both chains), `data/` (this workflow), `simulation/` |

This folder keeps only what is specific to real data: raw-data reading (`ReadEvent.py`)
and the Snakemake entry points.

All configuration files are in `muraves_lib/configuration/` (see its README):
the reconstruction parameters are `shared/reco_parameters.json` (used by data and simulation)
plus `data/data_parameters.json` (used only here); the electronics maps
(`data/electronics_mapping/`) and the 1phe benchmark files (`data/pedestal_1phe_values/`) are
data-only too. To change a value for a specific processing without touching these files, put
only that value in a JSON file and set it as `execution_config.reco_override_file`: it is merged
on top of the package parameters. The override may only use keys that exist there, in the same
section (e.g. `{"strips": {"n_strips": 32}}`): a misspelled or misplaced key stops the job with
an error listing it, instead of being silently ignored.

The Snakefile puts the repository root on `PYTHONPATH`, so jobs always use `muraves_lib` from this
checkout, even if the container image was built with an older copy of the package.

## 1) Before you run

Check the configuration files loaded by the Snakefile:

- `config.yaml` (local run settings)
- `../../tag/requirements.yaml` (contains `version`)

## 2) How to edit `config.yaml`

The most important fields are:

### `data_path`

This path point where the raw files are stored. On T2B that would be: 

```yaml
data_path: "/pnfs/iihe/muraves/muraves_DATA"
```
Inside `muraves_DATA` there are the folders RAW_GZ, PARSED, PEDESTAL, ... . Make sure this path is accessible from where you execute the snakefile (working node, condor node, local machine, ...)

### `copy_to_data`

- `True`: final outputs are written under `data_path`
- `False`: final outputs are written under `home_output_path`

### `home_output_path`

Where outputs go when `copy_to_data: False`. Default `"$HOME/muraves_outputs"`; environment
variables are expanded, so each user writes into their own home.

### `container`

Singularity image used by every rule. By default it is the shared image in
`/group/Muography/MURAVES/container/`: you don't need to change it. See
[`condor_submit/README.md`](../../condor_submit/README.md#the-container-image).

### `hodoscope`

YAML list of detector colors to process.

Example:

```yaml
hodoscope:
  - NERO
  - BLU
  - ROSSO
```

### `batch_size`

Number of runs grouped into one batch when `run` is provided.

### `threads`

Threads requested per rule.

### `run` and `batch_idx` (most important)

The workflow supports two selection modes:

1. Run-based selection (`run` set): the pipeline parses selected run IDs, creates batches of size `batch_size`, then processes all generated batch indices.
2. Batch-index selection (`run` empty): the pipeline directly uses `batch_idx`.

In practice:

- If `run` is non-empty, it takes precedence.
- If `run` is empty, `batch_idx` is used.

Accepted syntax for `run`:

- Single run: `"2546"`
- Comma-separated list: `"2500,2509,2512"`
- Inclusive range: `"2402-2412"`
- Mixed: `"2402-2412,2500,2509"`

Accepted syntax for `batch_idx`:

- Single batch index: `"1500"`
- Multiple: `"10,12,20"`
- Range: `"0-5"`
- Mixed: `"0-5,8,10"`

### `logs_on_console`, `verbose`, `overwrite_outputs`

- `logs_on_console`: print stage logs in terminal
- `verbose`: one of `debug`, `info`, `warning`, `error`, `critical`
- `overwrite_outputs`: rerun and overwrite already existing outputs when `True`

### About `type`

This filed isn't necessary for rules (`2_PedAna`) and (`3_MainRecSof`).

If the input of rule all is the output of the track reconstruction, `Snakefile` resolves the needed data types through rule dependencies (`ADC` and `PIEDISTALLI`).
The `type` key in `config.yaml` is currently not required by `rule all` in this version.

## 3) Minimal configuration examples

### Example A: run specific run IDs
The following configuration file will create 1 jobs: 1 batches of 10 runs (`batch_size`), each rule will require 2 cores. If you would give a range of run like ""2500-2515", it would create 2 jobs: 2 batches, one with 10 runs and the other with the remaining 6 runs.
```yaml
data_path: "/pnfs/iihe/muraves/muraves_DATA"
copy_to_data: True

batch_size: 10
threads: 2

hodoscope:
  - NERO

type:
  - ADC
  - PIEDISTALLI

batch_idx: ""
run: "2500-2509"

logs_on_console: True
verbose: info
overwrite_outputs: False
```

### Example B: run by batch index only
This is the standard way to process data on htcondor. Batches of 100 runs with 2 or 4 cores per rule. Batch idx in this case goes from 0 to 100, meaning that it will process 10 000 runs of NERO.
```yaml
data_path: "/pnfs/iihe/muraves/muraves_DATA"
copy_to_data: True

batch_size: 100
threads: 2

hodoscope:
  - NERO

type:
  - ADC
  - PIEDISTALLI

batch_idx: "0-100"
run: ""

logs_on_console: True
verbose: info
overwrite_outputs: False
```

## 4) Run the workflow with Snakemake (inside the container directly)

```bash
cd Software/muraves/tracks_reconstruction/
```

```bash
snakemake -n 
```

Execute:

```bash
snakemake --cores n
```

Notes:

- Increase `--cores` only if your environment can run multiple jobs safely.

## 5) Run the workflow with Snakemake on HTCondor

Setup, submission and the container image used by the jobs are explained in
[`condor_submit/README.md`](../../condor_submit/README.md). In short, once the profile is set up:

```bash
snakemake --profile <my_profile> -n   # list the jobs
snakemake --profile <my_profile>      # submit them
```

## 6) Where outputs are written

Final stamp target produced by `rule all`:

```text
{output_path}/GOLDEN_SELECTION/{color}/{version}/Track4p_batch{batch_idx}.stamp
```

Intermediate outputs of the main reconstruction stay in
`{output_path}/RECONSTRUCTED/{color}/{version}/` (`MURAVES_AnalyzedData_run<N>.root`, `MURAVES_miniRunTree_run<N>.root`, ...).

### Golden selection output (`Track4p_run<N>.root`)

Tree `Tracks4ptree`, one entry per golden event (`BestTrack_3p_ChiSquare_xz != -1` and `BestTrack_4p_ChiSquare_xz != -1`, as in the original `AnalysisOfCluster_and_tracks4planes.C`). Branch names are the ones of the C++ macro:

- track: `Theta`, `Phi`, `Scattering_xz/xy`, `ChiSquare_xz/xy` (4 planes), `ChiSquare_3p_xz/xy`
- for each plane `Z1..Z4`, `Y1..Y4`: `TrackClusterEnergy/Position/Size/Exp_<plane>`, `TrackClusterMax/MinStripEnergy_<plane>`, `ClusterMultriplicity_<plane>` and the clusters not on the track `NonTrackClusterEnergy/Size/Position_<plane>`
- run: `Run`, `TriggerRate`, `RunDuration`, `WorkingPoint`, `Timestamp` (per-event timestamp of step 3; replaces the C++ `Datetime`)

`RunDuration` [min] is computed from the event timestamps, (latest − earliest) / 60000, so the run-level tree is not needed.

A run without golden events (or without any event) gets an empty `Tracks4ptree`. Step-3 files produced before `BestTrack_4p_ClusterIndex_xz/xy` existed (v1.0.0) are still supported: the plane-4 cluster is recovered from the 4p candidates (the one whose `chiSquare_4p` and `ScatteringAngle` equal the stored best values). `4_GoldenSelection/validate_golden_selection.py` cross-checks the output against an independent event loop on the step-3 `.jsonl` (used by the CI).

`output_path` is:

- `data_path` if `copy_to_data: True`
- `home_output_path` (default `$HOME/muraves_outputs`) if `copy_to_data: False`

`version` is read from `../../tag/requirements.yaml`.

## 7) Troubleshooting

- No jobs selected:
  - check that `run` or `batch_idx` is not empty
  - if both are set, remember `run` wins
- Missing input files:
  - verify `data_path/RAW_GZ/{hodoscope}` exists and is visible from the runtime environment
- Existing outputs skipped:
  - set `overwrite_outputs: True` if you need to regenerate files

