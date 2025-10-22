:construction: <span style="color:yellow">**Documentation under contruction** </span>

MURAVES data analysis
========================

# Muraves environment - Docker

The `muraves-env` docker image is used to perform the analysis of MuRaVes data.



## Use the container on T2B

*The image has been already built. So this isn't really an installation, rather instructions on how to run the container from T2B.*

The image of the container is available on T2B as `.sif` image (Docker isn't available on T2B, 'singularity' has been used). To run the image the user has to login into T2B, go to `/group/Muography` and run the command:
```
./run_muraves_env.sh
```
This is an executable that will automathically:
- Run the image `/group/Muography/container/muraves-env.sif`
- Activate the muraves mamba environment with ROOT, python3 and other usefull packages.
- Return a welcome message
- Check that in the workspace there is a git reposotory. 
- **important**: The workspace is set to be the MuRaVes Git repository on T2B located in `/group/Muography/Software/`. This is a read-only folder with the only objective to run stable release of the MuRaVes software. This means you cannot modify or create new script here. If the use wish to use the container for developing purposes it is of course possible [Check this instructions](#container-in-developing-mode)!

The container is up and running is you see this output:
![image](/Software/documentation/WelcomeContainer.png)

### Container in developing mode 
The user can use this container mounting any other folder. This means that they can have any other folder available inside the container. The path can be changed by modifing the variable `WORKSPACE_HOST="/group/Muography/<whatever/folder>"` in the `/group/Muography/run_muraves_env.sh` file.

**The container is ready to be used in developing mode: all the changes on the scripts or more in general in the workspace will persist after the logout.**

## Local installation
*For the local execution of MuRaVes script, the user is free to set up the preferred environment. One possibility is to use the container available in this Git repository: in the `/environment/docker/` folder are available the Dockerfile and a bash script `entrypoint.sh` that are needed to build the image of the container.*

The following steps leads to the installation of the container.
- I don't have a MuRaVes Git repository -> [Steps](#i-do-not-have-a-muraves-repo-yet)

- I have already a the MuRaVes Git repository cloned on my laptop -> [Steps](#i-have-a-muraves-repo).

### I do not have a MuRaVes repo yet
1. Clone the entire repository locally using `git clone`:
   ```bash
   git clone https://github.com/muraves/Software.git 
   ```
2. Enter the folder where the docker file is located `~$ cd Software/environment/docker/`, and run:
   ```bash
   docker build -t muraves-env .
   ```
3. Now you can run the image and choose the working directory, for instance:
   ```bash
   docker run -it -v <~/my/local/folder>/Software:/workspace muraves-env
   ```
   By giving the path `<~/my/local/folder>/Software` before `:/workspace`, it means that all the script locally available inside this folder will be available also in the container. **The changes that the user applies while working in the container will persists once the container il closed.**
4. The user is now ready to go: develop or run scripts.

### I have a MuRaVes repo
1. Pull last changes from Git by running `git pull` from the `Software` directory.
2. Enter the folder where the docker file is located `~$ cd Software/environment/docker/`, and run:
   ```bash
   docker build -t muraves-env .
   ```
2. Now you can run the image and choose the working directory, for instance:
   ```bash
   docker run -it -v <~/my/local/folder>/Software:/workspace muraves-env
   ```
   By giving the path `<~/my/local/folder>/Software` before `:/workspace`, it means that all the script locally available inside this folder will be available also in the container. **The changes that the user applies while working in the container will persists once the container il closed.**
3. The user is now ready to go: develop or run scripts.


# Container installation - for mainteiners
T2B do not support docker. Therefore a few step are necessary in order to bring the container there.
- Apply of the changes to the dockerfile locally.
- Build the image locally as explained [here](#i-have-a-muraves-repo)
- Save the image that you created as `.tar` file
  ```bash
  docker save muraves-env:latest -o muraves-env.tar
  ```
- Copy the tar file on T2B. Better using rsync as it is a file of ~6GB:
  ```bash
  rsync -avP /home/biolchini/Documents/muography/MURAVES/Software/environment/docker/muraves-env.tar  abiolchi@mlong.iihe.ac.be:/group/Muography/container/.
  ```
  Remember to substituting the path and the username.
- Login to T2B and build the image using 'singularity':
  ```bash
  singularity build muraves-env.sif docker-archive://muraves-env.tar
  ```
- From here, if I run the image using `singularity shell --bind <my/folder>:/workspace muraves-env.sif`, the bash file called `entrypoint.sh` will not be runned, therefore the mamba environment will not be automatically activated. 
- To simplyfy user's life I wrote a wrapper `run_muraves_env.sh` that run the image and call `entrypoint.sh`.
- To conclude make the wrapper an executable by running
  ```bash
  chmod +x run_muraves_env.sh
  ```
- Now run
    ```bash
     ./run_muraves_env/sh
    ```
  The container and the environment are running

# Access and modify scripts easily - VSCode








# Muraves environment - Mamba
*The `muraves` package is used to perform the analysis of muraves data.*
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
