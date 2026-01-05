#!/bin/bash
# -----------------------------
# Wrapper script to run muraves-env.sif on T2B
# -----------------------------
# This file isn't needed to build the image.
# It is needed to
# - run the container
# - automatically activate the mamba environment 
# - Check existance of Git repository in the binded worspace


# Path to your Singularity image
SIF_PATH="/group/Muography/MURAVES/container/muraves-env.sif"

# Bind your workspace (host repo directory)
WORKSPACE_HOST="path/to/your/git/repo"
WORKSPACE_CONTAINER="/workspace"

DIR_HOST="/pnfs/iihe/muraves/muraves_DATA"
DIR_CONTAINER="/data"



# If no command is passed, default to bash
if [ $# -eq 0 ]; then
    CMD="bash"
else
    CMD="$@"
fi


# Execute entrypoint inside the container
singularity exec --bind ${WORKSPACE_HOST}:${WORKSPACE_CONTAINER},${DIR_HOST}:${DIR_CONTAINER} \
    --pwd ${WORKSPACE_CONTAINER} \
    ${SIF_PATH} /workspace/Software/environment/docker/entrypoint.sh ${CMD}
    
    # this would be the correct way to call it when entrypoint.sh is definitive.
    #${SIF_PATH} /usr/local/bin/entrypoint.sh ${CMD}


