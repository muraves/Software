"""Reconstruction core shared by the MURAVES data and simulation chains.

Modules:

* ``reco_config``         layered configuration (package defaults + workflow files);
* ``cluster_lists``       strip clustering (``CreateClusterList``);
* ``tracking``            3-plane / 4-plane track building (``MakeTracks``);
* ``angular_coordinates`` track angles (``TrackAngularCoordinates``);
* ``golden_selector``     golden-track definition (``is_golden``).

Workflow-specific code (raw data reading, I/O, Snakemake entry points) stays in
the workflow folders and imports from here.
"""
