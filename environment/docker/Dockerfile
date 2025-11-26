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

# Automatically activate environment
RUN echo "conda activate muraves" >> ~/.bashrc
SHELL ["bash", "--login", "-c"]
SHELL ["conda", "run", "-n", "muraves", "/bin/bash", "-c"]


# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Add entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace

# Run entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
