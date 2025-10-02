:construction: <span style="color:yellow">**Documentation under contruction** </span>

MURAVES data analysis
========================

The `muraves` package is used to perform the analysis of muraves data.


# Muraves environment

## Install

Install Miniforge as explained here https://github.com/conda-forge/miniforge. \
(*This documentation shows Miniforge, but you could choose Anaconda or Miniconda instead (Go to section [Install Miniconda](https://gitlab.cern.ch/LHCb-RD/ewp-bd2ksteeangular-legacy/-/tree/master/b2kstll?ref_type=heads#install-miniconda3). Miniforge has the advantage to have mamba as well which is faster than conda.*)

* Choose what to download based on you OS. For Ubuntu/Linux: download this [Miniforge3-Linux-x86_64.sh](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh)
* Execute the file `bash Miniforge3-Linux-x86_64.sh`
* Follow the instructions for installation
* Once miniforge is installed, it will ask a question concerning its activation. Answer yes, this way you can use mamba directly.
* Once installed, remember close and open again the termial or to source the bashrc file. In this way the modification will be effective.


## Create environment

Nominally, use the following method to install the package:\
    (*This exaple use `mamba` which works with Miniforge. If you use Anaconda or Miniconda you can use the same command replacing `mamba` with `conda`.*)

``` bash
mamba create -n muraves python=3.11 iminuit root uv -c conda-forge
``` 

This will create an enviroment called **muraves**. In order to activate it, do :

```bash
mamba activate muraves
```
Once inside the enviroment, you can clone muraves GitHub repository, if not done already.

:construction: <span style="color:yellow">**Work in progress** </span>
The necessary packages to run muraves reconstruction and analysis are still to be fully defined. For the moment this environment only has the essetials: root, python and minuit for basic minimisations.


# Troubleshooting

## Error importing zfit

If the error looks like `ImportError: /lib64/libstdc++.so.6: version `GLIBCXX_3.4.20' not found`, you can solve the problem by giving the correct path to the file. Follow the steps:
* Check if the file ` libstdc++.so.6` is in your mamba environment: 

```bash
    ls <mypath>/miniforge3/envs/muraves/lib/
```
* If the file is there just type:

```bash
    export LD_LIBRARY_PATH=<mypath>/miniforge3/envs/muraves/lib/:$LD_LIBRARY_PATH
```

This command can go in the `~.bashrc` as well. In this was it is automatically called everytime a new terminal is called.

* If the file is not there, you can seach where it is and give the correct path to it.

# Install Miniconda3

In order to install miniconda3, run this:

```bash
    curl -o ./install_miniconda3.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash install_miniconda3.sh
```
when prompted, select the path where you want to install it. It's not a good idea to install that in your home folder, but rather in a place not too limited by space. 

ATTENTION : Do not add the default ``conda initialize`` commands to your .bashrc.

Instead, add this to your .bashrc :

```bash
    source /path/to/your/miniconda3/etc/profile.d/conda.sh
    export CONDA_BASE=$(conda info --base)
```
Now you should be able to create and activate an environment.

Compatibility
-------------

Licence
-------

Authors
-------

The file was written by the [Alice Biolchini](mailto:alice.biolchini@uclouvain.be).
