# Tracks Reconstruction Pipeline (Snakemake)

This folder contains the MURAVES tracks reconstruction workflow orchestrated by Snakemake.

The main entrypoint is:

- `Snakefile`

The workflow runs the following stages:

1. Parse raw files (`1_Parser`)
2. Build pre-reconstruction products (`2_PreRec`)
3. Compute pedestal products (`3_PedAna`)
4. Run main reconstruction (`4_MainRecSof`)

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

This filed isn't necessary for rules (`3_PedAna`) and (`4_MainRecSof`).

If the input of rule all is the output of the track reconstruction, `Snakefile` resolves the needed data types through rule dependencies (`ADC` and `PIEDISTALLI`).
The `type` key in `config.yaml` is currently not required by `rule all` in this version.

## 3) Minimal configuration examples

### Example A: run specific run IDs
The following configuration file will create 10 jobs: 10 batches of 10 runs, each rule will require 2 cores.
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
run: "2500-2599"

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

1. Create a conda environemt with snakemake inside: `conda create -c conda-forge -c bioconda -c nodefaults -n snakemake snakemake`
2. In order to manage the submission you need: `pip install snakemake-executor-plugin-htcondor` 
3. Copy the profile configuration file provided in this GitHub repository `Software/condor_submit/profile/config.yaml`, in you T2B folder `$HOME/.config/snakemake/<my_profile>/.`

4. Once this is done, you're ready to go. Jobs that will be submitted can be checked as follows:
    ```bash
    snakemake --profile <my_profile> -n
    ```
5. The same command without `-n` will actually submit the jobs.

*Troubleshooting:* If you have more that one conda environment it can potentially mix up things. I kept seeing this error: 

    ```bash
    Traceback (most recent call last):
      File "/user/abiolchi/.config/snakemake/htcondor/grid-submit.py", line 4, in <module>
        import htcondor
    ModuleNotFoundError: No module named 'htcondor'
    ```
Cleaning a few conda environment solved this issue.

## 5) Where outputs are written

Final stamp target produced by `rule all`:

```text
{output_path}/RECONSTRUCTED/{color}/{version}/MURAVES_AnalyzedData_batch{batch_idx}.stamp
```

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
