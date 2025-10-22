#!/bin/bash
set -e


# -------------------------
# Welcome message
# -------------------------
echo " ~~~~~~~  Welcome to the MURAVES Containter 0.0 ~~~~~~~~  "
echo "                      .-----. "
echo "             .----. .'       ' "
echo "            '      V           '  "
echo "          '                      ' "
echo "        '                          '   "
echo "      '                              ' "
echo "       _  _        _   _        _  _  "
echo "      |  V | |  | |_| |_| \\  / |_ |_  "
echo "      |    | |__| | \\ | |  \\/  |_  _| "
echo
echo " ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  "

# -------------------------
# Activate conda environment
# -------------------------
if [ -f "/opt/conda/etc/profile.d/conda.sh" ]; then
    source /opt/conda/etc/profile.d/conda.sh
    conda activate muraves
else
    echo "ERROR: Conda not found in /opt/conda"
    exit 1
fi


# Check if /workspace is empty or not a git repo
if [ ! -d "/workspace/.git" ]; then
    echo "[WARNING:] No Git repo found in /workspace. "
    # git clone --depth 1 https://github.com/muraves/Software.git /workspace
    # chmod -R a-w /workspace   # make read-only
else
    echo "Detected existing Git repo in /workspace."
fi

# Start bash (or whatever CMD is given)
exec "$@"
