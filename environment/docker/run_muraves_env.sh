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
SIF_PATH="/group/Muography/container/muraves-env.sif"

# Bind your workspace (host repo directory)
WORKSPACE_HOST="/group/Muography/Software"
WORKSPACE_CONTAINER="/workspace"

# If no command is passed, default to bash
if [ $# -eq 0 ]; then
    CMD="bash"
else
    CMD="$@"
fi


# Execute entrypoint inside the container
singularity exec --bind ${WORKSPACE_HOST}:${WORKSPACE_CONTAINER} \
    ${SIF_PATH} /usr/local/bin/entrypoint.sh ${CMD}

