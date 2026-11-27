# simReco_muraves

Simulation-to-reconstruction bridge for the MURAVES detector.

This package adapts simulated detector data to the MURAVES reconstruction chain and provides a validated end-to-end workflow from detector hits to final golden-track output.

## Reconstruction Chain

```text
Simulated HitData
    ->
Bar-level aggregation
    ->
Digitization (energy or pathlength)
    ->
Plane construction
    ->
Official MURAVES clustering
    ->
ClusteredData ROOT output
    ->
Tracking reconstruction
    ->
TrackedData ROOT output
    ->
Golden-track selection
    ->
Tracks4ptree-compatible ROOT output
```

## Package Structure

```text
simReco_muraves/
├── cli/
├── clustering/
├── golden_tracking/
├── io/
├── models/
├── tests/
└── tracking/

scripts/
└── run_chain.sh
```

Each subpackage keeps its tests in its own `tests/` folder.

## Main Components

### Phase I: Detector Response and Clustering

Implemented in:

```text
simReco_muraves/clustering/
```

Responsibilities:

- Geant4 hit aggregation
- Strip mapping
- Detector-response digitization: energy x Poisson, or path length x Landau NPE/cm
- Plane construction
- Official MURAVES clusterization
- ClusterRecord generation

### Phase II: Tracking Reconstruction

Implemented in:

```text
simReco_muraves/tracking/
```

Responsibilities:

- Cluster-to-event organization
- Track reconstruction
- Angle reconstruction
- TrackingResult generation
- TrackedData ROOT output support

The tracking itself is `MakeTracks` and `TrackAngularCoordinates` from
`muraves_lib.reco`, the code the data chain runs;
`simReco_muraves/tracking/` adapts the simulated events to it.

### Phase III: Golden Reconstruction

Implemented in:

```text
simReco_muraves/golden_tracking/
```

Responsibilities:

- Golden-track selection
- Event/result consistency checks
- Experimental-compatible output
- Tracks4ptree output generation
- Final ROOT writing

---

## Installation

The simulation reconstruction is part of the MURAVES Software package
and is installed with it, from the repository root (`Software/`):

```bash
pip install -e ".[sim]"
```

An editable install puts `simReco_muraves` and `muraves_lib` on the
import path and registers the command-line entry points.

The `sim` extra brings uproot, awkward, numpy and SciPy (>= 1.16,
for the Landau draw of the path-length digitizer).

To run the test suite as well, add the development extra, again from
the repository root:

```bash
pip install -e ".[sim,dev]"
python -m pytest -q
```

`pytest` is not a runtime dependency, so a plain install will not
provide it.

## Production Entry Points

Each stage can be run either as a console script or as a module:

Clusterization (simulated hits -> ClusteredData):

```bash
muraves-simCluster <hit_root_file> --detector NERO -o OUTPUT_DIR
python -m simReco_muraves.cli.run_clusterization <hit_root_file> --detector NERO -o OUTPUT_DIR
```

Tracking (ClusteredData -> TrackedData):

```bash
muraves-simTrk <clustered_root_file_or_directory>
python -m simReco_muraves.cli.run_tracking <clustered_root_file>
```

Golden reconstruction (ClusteredData or TrackedData -> Tracks4ptree):

```bash
muraves-simGTrk <root_file_or_directory>
python -m simReco_muraves.cli.run_gTrks <root_file>
```

`--help` on any of them lists the available options.

### Outputs: where and how they are written

- **Clustering** writes into the directory given with `-o` (required).
  It refuses to start if that directory already holds chunks of the
  same prefix (`<prefix>_partNNN.root`), so chunks of two runs are never
  mixed. `--force` replaces them: at the end of the run, the chunks it
  does not rewrite are removed.
- **Tracking and golden** write one output file per input file:
  `-o FILE` (for a single input), or by default next to the input, with
  `_clustered` or `_tracked` in the name replaced by `_tracked` or
  `_golden`. An existing output is refused unless `--force` is given.

No tool writes at the destination directly, so they work on `/pnfs`
(dCache), where files can only be copied in. Each output is first
written to a private scratch folder, together with its provenance, then
copied next to its destination as `<name>.tmp`, given group read and
write permissions (`0664`) and renamed into place
(`muraves_lib.file_handler`: `scratch_to_output`, `copy_into_place`).
Output folders the tools create are group-writable (`0775`).
Clustering keeps all its chunks in scratch until the end of the run,
since their provenance holds the run totals, so the scratch folder
needs room for the whole clustered output of one input file.

The scratch folder is made in the system's temporary folder, which
follows `$TMPDIR`, or in `--scratch-dir DIR`. It is removed at the end,
whether the run succeeded or not; only a job killed outright can leave
a `muraves_scratch_*` folder behind (or a `<name>.tmp` next to the
destination, if killed during the copy).

A run that fails exits non-zero and leaves nothing under its output
names: no empty or partial file that the next stage could take for a
good one. With `--force`, the earlier output it was replacing is
removed as well.

A configured output location for productions (the simulation's
equivalent of `data_path`) is left to the production workflow, #28.

### Detector and geometry

`--detector` is required at clustering; its choices are the detectors
with a geometry in the shared configuration (NERO, ROSSO, BLU). It names
the simulated detector, is recorded in the `METADATA` of every output as
a required field, and goes into the output names
(`<stem>_NERO_clustered_partNNN.root`). The tracking and golden stages
reconstruct with that detector's geometry, its entry in
`muraves_lib/configuration/shared/reco_parameters.json`
(`detector_geometry`), which is the same entry the data chain uses: the
simulated productions are generated with exactly that geometry.

They always take the detector from their input. An input that records
none (clustered before the detector was recorded), or whose record
cannot be read, is refused: cluster it again from its Geant4 hits, or
reconstruct it with the standalone repository's tag `standalone-final`.
`--detector` on these stages is only a check: if given, it must agree
with what the input records.

`fullRun_v3` was generated with an earlier Geant4 geometry (g4-sim
`bac9b35`) that is not in the configuration; it is reproducible from
the tag `standalone-final` of the standalone simReco-muraves repository.

### Running the chain end to end

```bash
muraves-simCluster  hits.root --detector NERO -o chain/
muraves-simTrk      chain/hits_NERO_clustered_part000.root
muraves-simGTrk     chain/hits_NERO_tracked_part000.root
```

`scripts/run_chain.sh` runs the whole chain, with one folder per stage.

The golden stage accepts either input type and detects which it has
been given. `--input-type {clustered,tracked}` asserts the expected
type and errors on a mismatch, rather than overriding detection.

Golden output derived from a clustered file and from the
corresponding tracked file resolve to the same default filename. That
is deliberate: the two routes are expected to produce identical
output, so the result does not depend on which one was taken, and the
route that was actually used is recorded in the file's provenance
rather than in its name.

The consequence is that producing both at once, in order to compare
them, needs `-o` or separate directories. An existing output is never
overwritten without `--force`.

```bash
muraves-simGTrk hits_NERO_clustered_part000.root -o g_clustered.root
muraves-simGTrk hits_NERO_tracked_part000.root -o g_tracked.root
```

Given a directory, `muraves-simTrk` and `muraves-simGTrk` take its
files by the tree they hold, not by their names, so their own earlier
outputs are never read as input: `muraves-simTrk` every file with
`ClusteredData`, `muraves-simGTrk` every file with `ClusteredData` or
`TrackedData`, or only those of `--input-type`. With the default
`--input-type auto`, a directory holding both the clustered and the
tracked version of a chunk is refused before anything runs, since both
would give the same golden file.

### Digitization parameters

Clusterization offers two digitization methods. The options choose
between them, and the choice is recorded in provenance as
`digitization_method`.

**Energy method** (`energy`, the default). Each bar's deposited energy
is converted with one factor for every plane, and the npe is drawn
from a Poisson distribution:

```bash
muraves-simCluster <hit_root_file> --detector NERO --pe-per-mev 8.5 --rng-seed 42
```

The default conversion factor is the one used for the Phase I-III
validation samples.

**Path-length method** (`npe_per_cm`). Each bar's Geant4 path length L,
in cm, is multiplied by one Landau draw per bar, using per-plane NPE/cm
from the good-run calibration file:

```bash
muraves-simCluster <hit_root_file> \
    --pe-per-cm-file --detector ROSSO --run-range 10061-11918 --rng-seed 42
```

`--pe-per-cm-file` without a path uses the calibration shipped in
`muraves_lib/configuration/simulation/` (`npecm_per_run_v1.json`); a
path selects another file. Put the input file first, so that it is not
read as the calibration path.
The option was previously called `--pe-per-mev-file`; it is now
`--pe-per-cm-file`, since the file holds NPE per cm rather than per MeV.

- observed nPE = L x Landau(mpv = NPE/cm of the plane, sigma = 2 NPE/cm),
  truncated to [mpv - 2 sigma, mpv + 7 sigma], with no Poisson on top.
  mpv is ROOT's Landau location parameter; the draw reproduces ROOT's
  `TRandom::Landau`.
- Each plane's NPE/cm is the mean over the selected good runs. Values
  that are null or outside [5, 15] NPE/cm are left out.
- `--detector` selects the calibration. `--run-range` is optional; without it, the
  detector's fallback setting is used, with a warning (NERO and BLU
  `wp25_a`, ROSSO `wp25_b`). A range spanning more than one setting
  also gives a warning.
- `--pe-per-mev` and `--pe-per-cm-file` cannot be combined, and
  `--run-range` is rejected without a file.

With a file, the run range (or the fallback setting) follows the
detector in the output names, e.g.
`<stem>_ROSSO_r10061-11918_clustered_partNNN.root` or
`<stem>_ROSSO_rwp25_b_clustered_partNNN.root`.

Provenance records the file path and its SHA-256, the detector, the
run range, the per-station NPE/cm actually used, and a calibration
summary: the good runs selected, the settings in the range, and per
plane how many runs were used, null or rejected. A station missing
from the factors is an error, never a silent default.

`--rng-seed` is a master seed. It drives both random processes in
clusterization, Digitization and the experiment's random
smearing of single-strip cluster positions, through seeds derived per
plane and per event (`simReco_muraves/clustering/seeding.py`). The
same input, seed and code therefore give identical output; the result
does not depend on processing order or chunk boundaries; and changing
one plane's inputs changes only that plane's random numbers. The
scheme in use is recorded in each file's provenance.

Output produced before this scheme was introduced is not reproducible.
Single-strip smearing then drew from an unseeded system source, so
re-running gave a slightly different golden selection each time, with
about 0.6% of golden events changing between runs.

---

## Validation

Canonical regression suite, from the repository root:

```bash
python -m pytest -q
```

The suite covers every stage:

| Area | What is tested |
|---|---|
| clustering | bar aggregation, plane building, digitization including seeding and per-station factors, the clusterizer's inputs, cluster records |
| tracking | the straight-line fit, candidate building in `MakeTracks`, the angle convention, event building, four-plane candidate selection, and whole synthetic tracks end to end |
| golden tracks | the projection shared by both routes |
| provenance | records, chaining, the `METADATA` record and its storage in ROOT files, reading older files, errors on unreadable records |
| detector | the detector a stage takes from its input, and its refusal of inputs that record none |
| outputs | writing through scratch, permissions, clustering's chunk replacement, directory inputs |

The end-to-end tracking tests double as a regression test for the
Phase II geometry bug: a straight track with known slopes must come
back with the angles those slopes imply, and running it on plane
indices instead of plane positions is shown to be caught.

Tests on the experiment's own code (`MakeTracks` and
`TrackAngularCoordinates` in `muraves_lib.reco`) are characterisation tests. They pin
current behaviour, including the quirks listed under *Observations on
the reused code*, so that changing any of it is a deliberate act. A
test pinning a quirk does not mean the quirk is correct.

Comparison and validation tools (route comparison, data/simulation
comparisons, reference samples) are not part of this package; they
belong to the validation pipeline.

## Provenance

Every output file carries a record of what produced it, in the data
chain's format: a JSON string under the key `METADATA` (a `TObjString`),
which `muraves_lib.root_wrapper.load_root_metadata` and
`print_metadata.py` read as they read the data chain's files. It holds:

- the data chain's keys, for the stage that wrote the file: `commit`
  (of this package's checkout), `latest_release`, `algorithms`,
  `generated_at`, and `detector_config_files`, the reconstruction
  parameter files with their SHA-256 and content. The NPE/cm
  calibration, when used, is recorded with its SHA-256 only;
- `detector`, the simulated detector (a required field, see above);
- `stages`, the lineage. Each stage appends a record to the lineage it
  inherits from its input, so a golden file records not only its
  tracking parameters but the digitization constant that made the
  clusters it descends from. A record holds the stage name, a UTC
  timestamp, the input and output paths (the final ones, not the
  scratch copy), the full git commit and whether the working tree was
  dirty, the package and library versions, and the parameters that
  stage actually used;
- `simulation_metadata_version`, the layout of this record.

```bash
muraves-sim --provenance hits_NERO_golden_part000.root
```

The record is written into the scratch copy of the output, before it is
copied to its destination, so it works on `/pnfs`. Writing it, and
reading the input's, are strict: a failure is an error and the stage
leaves no output. Only the git lookups are best-effort: outside a git
checkout, the commit is `unknown`.

Files written before `METADATA` hold the lineage in a one-entry
`Metadata` tree (or a `Metadata_json` string); they are still read.

Tracking records `depth_correction_applied: false`: the shared
configuration enables the depth correction of 2-bar clusters, but the
simulation does not pass cluster depths to `MakeTracks` yet (#32), and
`muraves-simTrk` logs a warning saying so.

Note that a golden file made from ClusteredData records one stage fewer
than one made from TrackedData, so two golden files whose physics
branches are identical still differ in their metadata. That is
intended: the lineage describes how the file was made.

### Schema version

The golden output carries a schema version, bumped whenever branches
are added, removed, renamed, or change meaning. It is not bumped when
only values change: a different digitization constant produces
different numbers in the same schema, and the parameter record is what
distinguishes those files.

| Version | Change |
|---|---|
| 1 | First versioned layout |
| 2 | Adds `BestTrack4pIsTexpNull_xz` / `_xy` |

The flags record how the plane-4 candidate was chosen: `-1` when no
four-plane promotion happened, `1` when it was promoted but no
candidate had a valid Texp so the first was used, and `0` when a valid
Texp was found. This mirrors `best_track_4p_is_texp_null_*` in the
experimental reconstruction.

## Command overview

```bash
muraves-sim
```

lists the chain and every command in it.

## Reused reconstruction code

Clustering and tracking are the experiment's own code, from
`muraves_lib.reco`, which the data chain runs too:

```text
muraves_lib/reco/cluster_lists.py
muraves_lib/reco/tracking.py
muraves_lib/reco/angular_coordinates.py
```

Sharing this code with the data chain is deliberate. Cluster and
track definitions are then identical between simulation and experiment
by construction rather than by agreement, which is what makes the
comparisons in the Phase I-III validation meaningful.

### Adaptation history

Two errors were found by putting simulation and reconstructed data
into the same format and comparing them. Both were in this package,
not in the main reconstruction:

- tracking was run on plane indices (`X_POS = [0, 1, 2, 3]`) instead
  of the physical detector geometry, which made the three-plane polar
  angle wrong by roughly a factor of three: 10.9 degrees became 32.4
  degrees once the real geometry was propagated;
- the four-plane angles were unimplemented here and always returned
  -1. The four-plane angular reconstruction from `MURAVES_reco.py` was
  ported across to fix it.

### Observations on the reused code

The following are **not** changed here. They are recorded so that the
next person reading this code does not have to rediscover them, and
because the first may be of interest to whoever maintains the
experimental reconstruction.

**Texp gate in `MakeTracks`.** Best-track selection is gated on

```python
if Texp_cl1[i] > 0 and Texp_cl2[j] and Texp_cl3[k]:
```

Only the first term tests the sign. The other two are truthiness
tests, so a negative Texp on plane 2 or 3 passes the gate while a Texp
of exactly zero fails it. Simulation is unaffected, because it passes
a time expansion of 1.0 (`simReco_muraves/time_expansion.py`). On the experimental side the gate is
therefore more permissive than the first term suggests. This is
expected to be revisited once the simulation timing study gives a
clearer picture of how Texp should be used, so it is deliberately left
alone for now.

**Plane-4 offset.** `Z_add[0..2]` are added to the plane 1-3 cluster
positions, but `Z_add[3]` is never applied to plane 4. This has no
effect today, since `z_add[3]` is 0.0 for NERO, ROSSO and BLU in
`reco_parameters.json`, but the asymmetry would matter if that ever
changed.

**Compact four-plane indexing.** `Track_3p_to_4p_index` gains an entry
only when plane 4 holds at least one cluster, while the nested
four-plane arrays gain a row whenever the extrapolated position lands
in acceptance. These cannot fall out of step in practice, because
plane-4 clusters are a per-event property and the condition is
all-or-nothing within an event. It is worth knowing if that structure
is ever reworked.

### Angular convention

`TrackAngularCoordinates` defines the polar angle as

```text
theta = atan( |dz| / sqrt(dx^2 + dy^2) )
```

that is, the elevation above the xy-plane rather than the angle from
the telescope pointing axis. This is the collaboration's agreed
convention and matches the experimental reconstruction, so simulated
and reconstructed angles are directly comparable.

Because `|dz|` is used, theta never spans both hemispheres. Forward
and backward quantities must therefore be derived from phi, not from
theta.

### Geometry

The geometry constants in the tracking and golden entry points are the
ones the Geant4 simulation was generated with (g4-sim commit
`bac9b35`), in metres:

```text
x_pos = [-0.26,  0.0,   0.262, 1.492]
z_add = [ 0.289, 0.249, 0.207, 0.0  ]
```

Reconstruction must use the geometry the hits were generated with, not
that of the detector being compared against. Until October 2026 the
entry points used the ROSSO working point instead (`x_pos` ending in
1.475, `z_add` starting 0.292, 0.251), which differs from the generated
geometry by up to 1.7 cm in X and 0.3 cm in Z. Outputs from that period
are identifiable by the `x_pos` and `z_add` in their provenance.

The simulated X positions coincide with NERO's and BLU's; the Z heights
match no detector exactly. Comparisons against NERO, ROSSO and BLU
therefore carry each detector's geometric differences from the
simulation.

The proximity cuts are not independent constants: they are
`proximity_sigma_multiplier` (5.0) times the corresponding sigma, so
`0.004 -> 0.020` and `0.0035 -> 0.0175`. They are currently written
out literally, so a change to sigma will not propagate to them
automatically.

---

## Status

Current state:

- Phase I implemented and validated
- Phase II implemented and validated
- Phase III implemented and validated
- Production code separated from diagnostics
- Regression suite passing
- Tracking implementation preserved
- Repository being prepared for publication and long-term maintenance
