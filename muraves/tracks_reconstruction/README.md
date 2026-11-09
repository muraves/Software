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
| `muraves_lib/reco/data/reco_parameters.json` | all reconstruction parameters (detector geometry, clustering, tracking, raw-data format, slow control) |

This folder keeps only what is specific to real data: raw-data reading (`ReadEvent.py`)
and the Snakemake entry points.

All parameters are in the single file `muraves_lib/reco/data/reco_parameters.json`. JSON has no
comments, so each section has a `_used_by` entry saying whether the data chain, the simulation
chain or both read it (keys starting with `_` are documentation only). To change a value for a
specific processing without touching the shared file, put only that value in a JSON file and set
it as `execution_config.reco_override_file`: it is merged on top of the shared parameters.
The override may only use keys that exist in the shared file, in the same section (e.g.
`{"strips": {"n_strips": 32}}`): a misspelled or misplaced key stops the job with an error
listing it, instead of being silently ignored.

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
- `False`: final outputs are written under `$HOME/muraves_outputs`

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

## 4) Run the workflow with Snakemake on htcondor

Snakemake has the possibility to customise profiles to manage jobs submission.

A profile is available in this repository `Software/condor_submit/profile/config.yaml`. 

1. Create a conda environemt with snakemake inside: `conda create -n <env_name> -c conda-forge -c bioconda -c nodefaults python=3.13.12 "snakemake==9.16.3"`
  - If you have mamba: `mamba create -n env_name  -c conda-forge -c bioconda -c nodefaults python=3.13.12 "snakemake==9.16.3"` <- This is faster.
  - If for some reason the pinned versions do not work, you can run this: `conda create -n snakemake_test -c conda-forge -c bioconda -c nodefaults python=3.12 "snakemake>=8”`
  - **If you don't have conda or mamba installed**: [Please refere to this installation guide](https://github.com/muraves/Software/blob/master/environment/README.md#install).
2. In order to manage the submission you need: `pip install htcondor==23.10.29 snakemake-executor-plugin-htcondor==0.1.2`. It is important to pin the versions here because recent releases are not compatible anymore with the T2B htcondor (maybe in the future they will.)
3. Copy the profile configuration file provided in this GitHub repository `Software/condor_submit/profile/config.yaml`, in you T2B folder `$HOME/.config/snakemake/<my_profile>/.` 
  - `$HOME` is your home directory when you connect to T2B you can check what it is by running `echo $HOME` on your terminal
  - You should already have a `.config/` folder in your home, but maybe you need to create a `snakemake` folder and also a folder with the name that you want to assign to the profile.
4. Test if htcondor works fine within this environment:
  - Try to run:
    ```
    python - <<'EOF'
    import htcondor2

    print("Creating Schedd...")
    schedd = htcondor2.Schedd()

    print("SUCCESS!")
    print(schedd)
    EOF
    ```
    You should get "SUCCESS!". If so you can run also
    ```
    python - <<'EOF' 
    import htcondor2 as htcondor 
    collector = htcondor.Collector("cm.wn.iihe.ac.be") 
    ads = collector.query( htcondor.AdType.Schedd, projection=["Name", "MyAddress"] ) 
    print(f"Found {len(ads)} schedds") 
    EOF
    ```
    You should get the number of schedds.
    If any of this test fails, it is very likley some version incompatibility with the htcondor installed in the environment and that used by T2B. If everything works fine, you can move on! 
5. A dedicated container (`.sif` image needs to be created). Please run the command in the following order. 

    ```bash
    cd Software/condor_submit/container/
    singularity build muraves-sing.sif muraves-sing.def
    ```
    These commands should run succesfully, without further actions. If this is not the case, please report the bug!
6. Copy the `.sif` image in your `$HOME` directory. This is the image used in the Snakefile. **NB:** You can also keep it keep it here, but then, remember to modify the path in the snakefile.
*A dedicated container is preferable as the `muraves_lib` package is direclty built it without istalling it everytime that the container is opened. This is only useful for a developing container.*
*The Snakefile anyway puts this repository on `PYTHONPATH`, so the jobs import `muraves_lib` from your checkout rather than from the copy built into the image: you don't need to rebuild the image after changing `muraves_lib`.*

7. Once this is done, you're ready to go. Jobs that will be submitted can be checked as follows:
    ```bash
    snakemake --profile <my_profile> -n
    ```
8. The same command without `-n` will actually submit the jobs.

### Environment setup Troubleshooting:
1. If you have more that one conda environment it can potentially mix up things. I kept seeing this error: 

    ```bash
    Traceback (most recent call last):
      File "/user/abiolchi/.config/snakemake/htcondor/grid-submit.py", line 4, in <module>
        import htcondor
    ModuleNotFoundError: No module named 'htcondor'
    ```
    Cleaning a few conda environment solved this issue.

2. The command `singularity build Software/condor_submit/container/muraves-sing.sif Software/condor_submit/container/muraves-sing.def` rise the following error: 
    ```
    New error: INFO: Creating SIF file... FATAL: While performing build: while creating squashfs: /usr/libexec/apptainer/bin/mksquashfs command failed: exit status 139
    ```
    Fixed by limiting number of processors used with squashfs: `apptainer build --mksquashfs-args "-processors 4" Software/condor_submit/container/muraves-sing.sif Software/condor_submit/container/muraves-sing.def`

## 5) Where outputs are written

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

A run without golden events gets an empty `Tracks4ptree`. `4_GoldenSelection/validate_golden_selection.py` cross-checks the output against an independent event loop on the step-3 `.jsonl` (used by the CI).

`output_path` is:

- `data_path` if `copy_to_data: True`
- `$HOME/muraves_outputs` if `copy_to_data: False`

`version` is read from `../../tag/requirements.yaml`.

## 6) Troubleshooting

- No jobs selected:
  - check that `run` or `batch_idx` is not empty
  - if both are set, remember `run` wins
- Missing input files:
  - verify `data_path/RAW_GZ/{hodoscope}` exists and is visible from the runtime environment
- Existing outputs skipped:
  - set `overwrite_outputs: True` if you need to regenerate files

