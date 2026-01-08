FROM condaforge/miniforge3:latest

# Set UTF-8 locales
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Create the environment
RUN mamba create -n muraves -y -c conda-forge -c bioconda\
    python=3.11 \
    root \
    iminuit \
    uv \
    pandas \
    polars \
    numpy \
    scipy \
    matplotlib \
    jupyter \
    zfit \
    snakemake \
    uproot && \
    mamba clean -afy

# ---- Apptainer-safe conda setup ----
ENV CONDA_ENVS_DIRS=/opt/conda/envs
ENV CONDA_PKGS_DIRS=/opt/conda/pkgs

ENV CONDA_DEFAULT_ENV=muraves
ENV CONDA_PREFIX=/opt/conda/envs/muraves
ENV PATH=/opt/conda/envs/muraves/bin:$PATH
ENV PS1="_MURAVES-Container_\[\e[32m\]\u@\h:\w\$ \[\e[0m\]"

# Automatically activate environment: specifico per container dockers
#RUN echo "conda activate muraves" >> ~/.bashrc
#SHELL ["bash", "--login", "-c"]
#SHELL ["conda", "run", "-n", "muraves", "/bin/bash", "-c"]



# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Add entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace

# Run entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]

##! Once muraves_lib is sully developed, better to put the installation here
##! so that the image can be used directly without mounting the code.
