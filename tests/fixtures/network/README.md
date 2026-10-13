# Prepared network integration fixture

- Author: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-13

## Summary

This prepared model contains 263 conduits, 263 junctions, three storage nodes,
two outfalls, four pumps and one weir. The complete companion GIS export has
nine datasets. It exercises realistic model content and partial field edits;
it is not an approved engineering update model.

Object IDs and all geographic geometry have been replaced together. Geometry
uses arbitrary local display coordinates in feet, with an unknown GIS coordinate
system. Hydraulic lengths and elevations remain engineering fields, independent
of display geometry. Descriptions, tags, reviewer names, identifying notes,
source fingerprints, external paths and original metadata have been removed.
The original external rainfall files were unavailable; inline zero rainfall
replaces those files. These models are therefore not hydraulically equivalent
to the original rainfall event.

The prepared baseline retains topology and hydraulic values. Those can still
fingerprint a source network. This fixture is **not certified anonymous for
external release**. Source data, replacement-ID mapping, preparation scripts and
privacy comparison tools remain outside this repository. Do not add them here.

### Inputs and expected behavior

- `baseline.inp`: prepared baseline with 25 sections and synthetic map geometry.
- `updates.json.gz`: portable counterpart of all nine rebuilt GIS datasets.
- `updates.gdb/`: rebuilt file geodatabase with unknown local CRS and no copied
  source metadata; use this for ArcGIS inspection rather than ordinary tests.
- `workload.json`: screened model scope, current existing/future decisions,
  approved partial fields and explicit engineering holds. Of 553 original
  priority 1/2 candidates in the prepared full workload, 310 associate with this
  model; 243 remain outside scope. Each scenario includes 309 candidates:
  239 priority 1 and 70 priority 2. One scoped priority 2 record is excluded.
  Connectivity screening establishes possible scope, not engineering approval.
- `reviewed_existing_changes.json` and `reviewed_future_changes.json`: 14
  diameter-only patches each. These use individually reviewed diameter authority,
  one-to-one GIS/model membership, matching endpoint IDs and matching baseline
  diameter. The source decisions currently agree for both scenarios.
- `expected_reviewed_updates.json`: independently supplied diameter expectations
  in inches and feet. For MGD flow units, SWMM circular diameter is in feet:
  **diameter_ft = diameter_in / 12**. Other fields remain unchanged.
- `existing_changes.json`: those 14 patches plus four instructions for one
  explicitly synthetic topology addition: junction, coordinates, conduit and
  circular cross-section.
- `future_changes.json`: those 14 patches plus two synthetic additions. The
  future-only selection is test input, not a change to source review decisions.
- `expected_synthetic_additions.json`: expected addition parameters, clearly
  distinguished from approved source values. Each test conduit is 100 ft long,
  with Manning roughness 0.013, 1-ft diameter, zero offsets/initial/maximum flow,
  and one barrel. New nodes have 12-ft maximum depth and an invert 1 ft above or
  below the existing anchor, giving a positive downstream slope of 0.01.
- `manifest.json` and `gdb_verification.json`: dataset coverage, caveats and
  readback/identity-replacement QA counts. Unknown-CRS ArcGIS storage quantizes
  synthetic XY; GDB/portable coordinates are checked within 0.001 display ft.
  Hydraulic attribute readback is checked exactly.

### Holds and manual review

Priority 1 records still require finished engineering direction, node parameters,
roughness, shape, offsets and loading/boundary decisions. Elevation, datum,
aggregation and length holds remain unresolved. The 14 reviewed diameter patches
do not resolve other issues on those pipes. No automated priority-to-edit
conversion is asserted.

Inspect the expected field values, conduit endpoint connectivity, added-node
inverts, audit source keys, and unchanged controls, loading, patterns, curves and
event records. A successful structural test does not demonstrate acceptable
hydraulic performance. Do not compare synthetic map lengths with hydraulic
conduit lengths or interpret the map as a real geographic network.

## Developer README

Use the repository Python 3.12 environment with the modern `hymo.document`
reader. Run `python -m pytest tests/test_fixtures.py -q` for portable acceptance
and fixture-contract checks; no ArcGIS dependency is needed. Tests verify both
scenarios, source input preservation, deterministic preview/application, reviewed
diameter conversion, synthetic additions, untouched records and unrelated
section bytes, stale-baseline rejection, neutral identifiers, and local geometry.

Load operation JSON into `shmm.editing.Change` records and use
`preview_changes`/`apply_changes` with `hymo.document.read_document`.
These operations return candidate bytes and an audit; the test suite writes to
temporary directories when checking publication. Generated candidates are not
production models. Missing source data is recorded in `workload.json` as
`STUB_FINISHED_CONDUIT`, `STUB_FINISHED_NODE`, `STUB_FINISHED_PATCH`,
`STUB_BASELINE_ASSOCIATION`, `STUB_REACH_ALLOCATION`, `STUB_DATUM_REVIEW` and
`STUB_LENGTH_REVIEW`, as applicable. A datum or length hold must not block an
independently approved diameter-only patch.

Keep the prepared fixtures and expected records versioned together. Regeneration
and original-identifier comparison occur outside SHMM; regeneration requires the
private replacement mapping. GIS binary row order and metadata are not used as
model-editing expectations. Engine checks, when available, are separate from the
structural tests and must state the pinned solver version and changed rainfall.
