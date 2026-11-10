MURAVES Software
===

Software for the analysis of the data of the MURAVES experiment (MUon RAdiography of VESuvius).
This repository takes the raw data of the three hodoscopes (ROSSO, NERO, BLU) through parsing,
pedestal/1phe calibration, track reconstruction and golden selection, up to the run selection and
the angular maps used for the physics analysis.

The most recently discussed topics can be found in the minutes of the
[MURAVES Indico agenda](https://agenda.infn.it/category/730/).

## Starterkit

*New to MURAVES? Start here.*

1. Set up your workspace and the container: [Starterkit](environment/README.md#starterkit).
2. Learn about the detector and the data files: [documentation/README.md](documentation/README.md).
3. Run the reconstruction pipeline: [muraves/tracks_reconstruction/README.md](muraves/tracks_reconstruction/README.md).

## Repository structure

| Folder | Scope | Details |
|---|---|---|
| [`environment/`](environment/) | Docker/Singularity container (`setup_muraves.sh`), mamba environment, editor and Jupyter setup | [README](environment/README.md) |
| [`documentation/`](documentation/) | Detector, trigger, run types, raw and parsed data formats, data access | [README](documentation/README.md) |
| [`muraves_lib/`](muraves_lib/) | Shared Python library: file handling, run manager, ROOT wrapper, Snakefile helpers and the reconstruction core (`muraves_lib/reco`), shared by data and simulation | — |
| [`muraves_lib/configuration/`](muraves_lib/configuration/) | All configuration files: reconstruction parameters, electronics mapping, pedestal/1phe benchmark values | [README](muraves_lib/configuration/README.md) |
| [`muraves/tracks_reconstruction/`](muraves/tracks_reconstruction/) | Snakemake pipeline: parser → pedestal → main reconstruction → golden selection | [README](muraves/tracks_reconstruction/README.md) |
| [`muraves/analysis/`](muraves/analysis/) | Good run selection (`select_runs.py`), angular maps and transmission | [README](muraves/analysis/README.md) |
| [`muraves/monitoring/`](muraves/monitoring/) | Run monitoring notebooks and plots (slow control, trigger rate, ...) | — |
| [`condor_submit/`](condor_submit/) | HTCondor profile and Singularity definition to run the pipeline on the T2B batch system | [tracks_reconstruction README](muraves/tracks_reconstruction/README.md) |
| [`tag/`](tag/) | Versioning of the workflow (`tag.notes`, `requirements.yaml`) | [tag.notes](tag/tag.notes) |
| [`test_data/`](test_data/) | Raw files of one NERO run (2500), used by the CI test of the pipeline | — |

## Versioning

Releases are tagged `vX.n.k`:

- `X` changes when the outputs change and the data must be reprocessed;
- `n` changes for substantial updates that keep the outputs compatible;
- `k` changes for bug fixes and documentation updates.

The description of every release is in [tag/tag.notes](tag/tag.notes); the list of releases is on
the [GitHub releases page](https://github.com/muraves/Software/releases).

## Maintainer

Alice Biolchini (alice.biolchini@uclouvain.be). Please report any problems you find.
