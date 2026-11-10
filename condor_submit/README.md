# Running the pipeline on HTCondor (T2B)

This folder contains what is needed to run the
[tracks reconstruction pipeline](../muraves/tracks_reconstruction/README.md) on the T2B batch
system:

| File | Content |
|---|---|
| [`profile/config.yaml`](profile/config.yaml) | Snakemake profile: submission through HTCondor, resources, Singularity options |
| [`container/muraves-sing.def`](container/muraves-sing.def) | Definition of the Singularity image used by the jobs |

The jobs run inside a shared image, already built and stored in
`/group/Muography/MURAVES/container/`. The image used is set by the `container` key of
[`muraves/tracks_reconstruction/config.yaml`](../muraves/tracks_reconstruction/config.yaml).
**You don't need to build it yourself**, see [The container image](#the-container-image).

## Setup (once)

1. Create a conda environment with snakemake inside:
   ```bash
   conda create -n <env_name> -c conda-forge -c bioconda -c nodefaults python=3.13.12 "snakemake==9.16.3"
   ```
   - If you have mamba, use `mamba create` with the same arguments: it is faster.
   - If the pinned versions do not work:
     `conda create -n <env_name> -c conda-forge -c bioconda -c nodefaults python=3.12 "snakemake>=8"`
   - **If you don't have conda or mamba installed**:
     [please refer to this installation guide](../environment/README.md#install-miniforge).
2. Activate it and install the HTCondor submission tools:
   ```bash
   pip install htcondor==23.10.29 snakemake-executor-plugin-htcondor==0.1.2
   ```
   The versions must be pinned: recent releases are not compatible with the T2B HTCondor.
3. Copy the profile into your T2B home:
   ```bash
   mkdir -p $HOME/.config/snakemake/<my_profile>
   cp Software/condor_submit/profile/config.yaml $HOME/.config/snakemake/<my_profile>/.
   ```
   - `$HOME` is your home directory on T2B (`echo $HOME`).
   - `<my_profile>` is any name you choose: it is the name you pass to `--profile`.
   - In the copied file, replace `<username>` in `htcondor-jobdir` with your T2B user name
     (`echo $USER`), and create that folder: `mkdir -p $HOME/muraves_outputs`.
4. Test that HTCondor works within this environment:
   ```bash
   python - <<'EOF'
   import htcondor2

   print("Creating Schedd...")
   schedd = htcondor2.Schedd()

   print("SUCCESS!")
   print(schedd)
   EOF
   ```
   You should get "SUCCESS!". If so, also run:
   ```bash
   python - <<'EOF'
   import htcondor2 as htcondor
   collector = htcondor.Collector("cm.wn.iihe.ac.be")
   ads = collector.query(htcondor.AdType.Schedd, projection=["Name", "MyAddress"])
   print(f"Found {len(ads)} schedds")
   EOF
   ```
   You should get the number of schedds. If either test fails, it is very likely a version
   incompatibility between the HTCondor in the environment and the one used by T2B.

## Submitting jobs

1. Edit [`muraves/tracks_reconstruction/config.yaml`](../muraves/tracks_reconstruction/config.yaml)
   (runs, batches, hodoscopes, ...), as explained in the
   [tracks reconstruction README](../muraves/tracks_reconstruction/README.md#2-how-to-edit-configyaml).
2. From `Software/muraves/tracks_reconstruction/`, check which jobs would be submitted:
   ```bash
   snakemake --profile <my_profile> -n
   ```
3. The same command without `-n` submits the jobs.

## The container image

The image contains the conda environment of the pipeline (python, ROOT, snakemake, ...) and a copy
of `muraves_lib`. The Snakefile puts the repository checkout on `PYTHONPATH`, so **the jobs import
`muraves_lib` from your checkout, not from the copy built into the image**: you don't need a new
image when `muraves_lib` changes. A new image is needed only when the software installed in it
must change (e.g. a new package in `muraves-sing.def`).

The images are named after the repository tag they were built from, e.g.
`muraves-sing_v0.5.0.sif`. Older images are kept, so a processing can be repeated with the image
it used.

### Building a new image (maintainers)

1. Build from a clean checkout of a tag, so that the name of the image matches its content:
   ```bash
   cd Software/condor_submit/container/
   TAG=$(git describe --tags)
   apptainer build --mksquashfs-args "-processors 4" muraves-sing_${TAG}.sif muraves-sing.def
   ```
   The build must run from this folder: `muraves-sing.def` copies `muraves_lib` with paths
   relative to it. The packages in `muraves-sing.def` are not pinned, so two builds of the same
   tag at different times can contain different package versions.
2. Copy the image to the shared folder:
   ```bash
   cp muraves-sing_${TAG}.sif /group/Muography/MURAVES/container/
   chmod 775 /group/Muography/MURAVES/container/muraves-sing_${TAG}.sif
   ```
3. Update the `container` key of `muraves/tracks_reconstruction/config.yaml` and commit it.

## Troubleshooting

1. `ModuleNotFoundError: No module named 'htcondor'`, e.g.
   ```
   Traceback (most recent call last):
     File "<home>/.config/snakemake/htcondor/grid-submit.py", line 4, in <module>
       import htcondor
   ModuleNotFoundError: No module named 'htcondor'
   ```
   Having more than one conda environment can mix things up. Removing the unused conda
   environments solved it.

2. `apptainer build` fails with:
   ```
   INFO: Creating SIF file... FATAL: While performing build: while creating squashfs: /usr/libexec/apptainer/bin/mksquashfs command failed: exit status 139
   ```
   Limit the number of processors used by squashfs with `--mksquashfs-args "-processors 4"`, as in
   the build command above.
