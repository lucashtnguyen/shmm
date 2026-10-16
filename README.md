# shmm

- Last modified by: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-16

## Summary

This is a personal open-source project. Contact the maintainer through the
[GitHub profile](https://github.com/lucashtnguyen). Project documentation,
source attribution and package metadata use GitHub contact links rather than
personal or employer email addresses.

SHMM was originally conceived to read shapefiles and write SWMM `.inp` files,
then expanded to read, modify, and write existing models. The modernization
goal is to **take finished, model-ready data and apply it to a new or existing
SWMM model**.

SHMM should also support GIS/model comparison so users can inspect the supplied
data against the baseline and see exactly which changes are going into the model.
It uses finished object IDs or an explicit crosswalk and distinguishes reported
differences from requested edits. Comparison can run without modifying a model.

Resolving asset associations, reach aggregation, scenario selection, datum
conflicts, and engineering parameters belongs to upstream project workflows.
SHMM compares finished inputs, validates and applies instructions, preserves
unrelated content, and records exactly what it wrote.

The [modernization specification](docs/modernization_spec.md) defines the
boundary, proposed input contract, requirements, acceptance tests, and
implementation sequence. Oregon City is the first intended integration;
its scope rules and unresolved GIS questions stay in that project's workflow.

### Current status and workflow

The first modernization increment is implemented on Python 3.12. **hymo reads
and interprets model text; SHMM modifies and writes it.** The new path supports
explicit additions and partial updates of junctions, conduits, circular or
force-main conduit cross sections, node coordinates, and add-only interior link
vertices. It preserves unrelated
text and produces a separate candidate plus a before/after audit.

SHMM 0.1.2 also produces baseline-to-proposed preview diffs and independent
baseline-to-written-model diffs, with source evidence and upstream QA flags.
Finished whole-section replacement now supports explicit final topology,
deletions, pump rewiring and forcing replacement with mandatory source hashes
and review evidence; see the section publication workflow below. Fine-grained
record deletion/rewiring, interactive map/profile review and complete section
semantics remain deferred. The
[section coverage matrix](docs/swmm_section_coverage.md) inventories 57 EPA
SWMM 5.2.4 sections and identifies implemented checks and deferred contracts.

The historical package exposes `shmm.load_template()` for the embedded template,
`shmm.INP(...)` for an existing input file, section tables such as `conduits`
and `coordinates`, and `write_SWMMInp(...)` for writing a file. Those concepts
remain available lazily for reference. They do not use the new preserving
editing path. The old README misspelled `load_template` and used obsolete
DataFrame append examples; those examples have been retired pending the new
interface. Legacy sections are represented as pandas DataFrames through `hymo`.

`shmm/gis.py` contains helpers for node coordinates, link vertices, and
subcatchment polygons. These format map geometry; they do not establish
hydraulic parameters, units, coordinate systems, or datum validity.

### Finished section publication

For an upstream-prepared final network, `SectionPatch` supplies a complete
section body, a unique `source_key`, a required `basis`, and optional
`object_evidence` keyed by model object ID. Bodies use individual text lines
without line endings; include the comments and existing records to retain.
Inline comments can identify interpolated values, literal placeholders and
merged source pipes. SHMM does not choose any of those engineering values.
An empty body explicitly clears the records; `delete=True` removes an existing
section. Unmentioned sections preserve their original text exactly.

`preview_section_patches` requires `baseline_sha256` and returns exact bytes,
an audit and a regular `ModelDiff`. It checks shared node/link ID collisions,
link endpoints, cross sections, coordinates, supported loads, curves and
timeseries references, controls, tags, profile lists and report selections.
Optional `require_connected=True` requires exactly one weakly connected group;
`require_terminal_routes=True` requires a declared directed route from every
node to an outfall. These checks follow declared endpoints, not simulated flow.
Outfalls themselves have valid zero-link terminal routes.

`publish_section_patches` publishes a **new** candidate, both JSON/CSV/HTML
comparisons and a completion audit. It refuses existing destinations, rechecks
the source, reads back the staged and published model, independently replays
the finished requests and verifies exact bytes. The source is never overwritten.
`compare_written_sections` can also independently check a separately published
model. Every section request retains complete before/after text, hashes and
basis; effect rows join the supplied object evidence. Unknown section bodies
remain literal, and syntax beyond the documented reference checks still
requires solver validation. A successful publication is faithful serialization,
not engineering acceptance of assumptions or a claim that the model runs.

Inspect both diffs and the audit before using the candidate. Confirm removed
objects have their controls, loads and geometry reconciled; inspect pump
outlets, terminal replacements, source memberships of merged pipes and all
assumption comments in a profile viewer. Require the completion audit and its
matching candidate hash; interruption can leave an incomplete transaction.
See [the handoff contract](docs/umdev_handoff.md#finished-section-contract).

### Shapefile export for model QA

`shmm.export_shapefiles` exports the actual written network as separate
`nodes.shp` and `links.shp` layers, with explicit CRS sidecars, hydraulic fields,
assumption/placeholder flags and component/island identifiers. It reads through
hymo and does not edit the INP or infer missing engineering values. All four
node and five link families participate, including pumps and storage.

Supply `GISAnnotation` / `GISFlag` records from the upstream preparation and the
exact candidate SHA-256. Each distinct flag gets its own integer GIS field;
`manifest.json` maps the short DBF names to complete flag names. `QA_KEY` joins
each feature to untruncated parameter-specific evidence in `qa_features.json`.
Unknown historical provenance stays `QA_COVER=unknown`; a number such as 12.345,
999 or 0.013 by itself never establishes a placeholder or assumption.

Symbolize `ISLAND_ID` to distinguish each unsupported new island, or `COMP_ID`
to show every component. Supply the original baseline so inherited independent
basins are preserved as baseline-connected components. `islands.csv` lists only
unsupported new islands; `components.csv` and `components.json` retain all groups
and their asset membership. Without a baseline, unanchored status is unknown.
Nominal graph routes are separate from hydraulic simulation.

Install the optional GIS dependencies with `python -m pip install -e ".[gis]"`.
Call the exporter from Python with the written hymo document, a new private
output directory, explicit `crs`, original `baseline` and finished annotations.
Missing coordinates produce null shapes with visible geometry flags; no assets
are silently dropped. Existing output directories are never overwritten. The
bundle is staged and read back before publication. Inspect `QA_COVER`,
`PLACEHOLDR`, `ASSUMED`, `PROVISION`, `QA_FLAGS`, individual flag fields and
`ISLAND_ID`; a missing flag is not proof of accepted engineering data.

See [the spatial export contract](docs/spatial_export.md) for field meanings,
units, shapefile limitations, the caller contract and manual review steps.
Run `python -m pytest tests/test_spatial.py` with the GIS extra installed. Tests
cover all families, exact vertices, case-insensitive identities, baseline basins,
new islands, null geometry, source preservation, stale evidence, long UTF-8 flags,
DBF readback, CRS, deterministic components and failed-publication cleanup.

### Inputs, outputs, and QA/QC

- New inputs are an explicit baseline INP and finished `Change` instructions.
  Each instruction names its action, section, object ID, supplied fields, and
  stable source key. Optional old-value and baseline-hash preconditions guard
  against stale inputs. Omitted update fields remain unchanged; null is rejected.
- Finished `VertexChange` instructions add ordered interior XY rows through the
  `vertex_changes` keyword on the same preview/apply/publication transaction.
  Supply only interior points, ordered inlet to outlet, in the baseline map
  coordinate system. The target link must exist in the candidate and both
  endpoint nodes need finite coordinates; same-batch additions are supported.
  Empty vertices represent a straight link. Existing vertex sets cannot be
  appended to or replaced. Map geometry never supplies hydraulic length or
  elevation, and SHMM does not infer or reproject coordinates.
- `preview_changes` and `apply_changes` return the exact candidate bytes and
  audit in memory. `edit_model` stages, reads back, and publishes a separate INP
  followed by its completion JSON audit. Existing files cannot be overwritten.
- The historical template/table writer remains separate and is not recommended
  for preservation-sensitive production edits.
- Modernization requires finished records in target SWMM field units, explicit
  IDs/operations, and compatible CRS/datum metadata.
- Implemented comparison outputs are structured JSON, a standalone filterable
  HTML report and a CSV table. `preview_model_diff` compares baseline to the
  proposed candidate before publication; `compare_written_model` compares an
  actual re-read candidate with baseline and independently replayed requests.
  Both retain requested operations, no-ops, actual effects, evidence and QA flags.
  Written verification checks exact expected bytes, including comments and opaque
  sections, and identifies missing/unexpected effects. Named fields use verified
  hymo schemas; all other cards use ordered lexical rows without collapsing
  repeated IDs. Map/profile renderers remain planned.
- The implemented audit records source keys, before/after fields, model settings,
  input/output SHA-256 hashes, actual changes, and validation limits. Readback
  confirms supplied values. The optional pinned engine check is distinct from
  model application and retains reports and binary results.
- Manually inspect edits, connectivity, offsets, dimensions, loading references,
  and geometry. Verify that unrelated controls, loads, and events are retained.
- Review differences outside the operation set and not-comparable records.
  Absence from a partial GIS export does not authorize model deletion.

### umdev handoff and manual review

umdev owns reusable utility GIS configuration, data cleaning, evidence selection,
engineering parameter assignments and unresolved-data QA. It hands SHMM finished
`Change`/`VertexChange` instructions, the baseline hash and evidence keyed by
instruction `source_key`. Keep project GIS, configuration and generated reports
outside the public repositories. SHMM does not infer parameters from raw GIS.

Generate a preview diff, publish the same instruction sequence with `edit_model`,
read the actual output with hymo, and generate the written-model diff. Require
`report['verification']['matches_expected']` before accepting publication
integrity. Inspect upstream QA flags and model profiles separately; a faithful
edit does not establish engineering acceptance. `write_diff_reports` publishes
non-overwriting JSON/CSV/HTML files; filter the HTML by asset ID, source basis or
QA flag. umdev supplies separate baseline/candidate topology reports for inherited
basins, introduced islands and possible held connectors. Review these alongside
both model diffs; SHMM does not resolve connector parameters or station policies.
See the [handoff contract and review procedure](docs/umdev_handoff.md).

For pressure pipes, umdev supplies an explicit `FORCE_MAIN` cross section,
its diameter and positive `geom2` pressure coefficient, plus the separate
conduit `roughness` field. `geom2` is Hazen-Williams C for `H-W`, or absolute
Darcy-Weisbach roughness height in inches (US) / millimetres (SI) for `D-W`;
it is never Manning n. SHMM checks touched force-main links/cross sections
against Dynamic Wave routing and the baseline's supported friction equation.
The documented EPA defaults apply when these options are absent: `DYNWAVE`
and `H-W`. Unrelated edits do not revalidate inherited pressure parameters.

Sealing is an explicit **junction** instruction: `surcharge_depth=999` means
999 additional model length units above the junction's maximum depth before
flooding. The project policy and node role belong to umdev: sealed pressure
connections receive the supplied value, while open discharge manholes and wet
wells retain their separately reviewed representation. SHMM does not seal every
endpoint automatically, invent a rim/floor, convert storage to a junction, or
infer a pump/curve/control from a GIS force-main label. Include the pressure
coefficient basis, node role, units, and any provisional sealing decision in
handoff evidence; inspect those effects in both review diffs. A 999 surcharge
allowance suppresses model flooding and is not a verified pressure rating.
These field meanings follow the [EPA SWMM 5.2 manual](https://www.epa.gov/system/files/documents/2022-04/swmm-users-manual-version-5.2.pdf)
and [EPA 5.2.4 solver defaults](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/project.c).

For a **new junction**, `Change.comment` can carry an upstream review annotation
directly into the INP row after ` ; `. It must be nonempty printable single-line
text; embedded line breaks or control characters are rejected. Comments on
updates or other section types are unsupported, so existing notes remain intact.
An upstream missing-rim policy can explicitly supply `max_depth=12.345` and
`comment="UMDEV_PLACEHOLDER_RIM MaxDepth=12.345 ft"` (or `m` in an SI model).
SHMM writes that literal **depth** even with `LINK_OFFSETS ELEVATION`; the offset
setting does not turn junction maximum depth into an absolute elevation. The
placeholder represents unresolved rim evidence, not a surveyed rim or accepted
node profile. SHMM does not choose the placeholder or clear its upstream QA hold.
The annotation appears in the edit audit, as a `comment` effect in both review
diffs, and in the model itself. Altered or missing written annotations fail
exact-byte reconciliation.

### Limitations and unresolved information

The legacy writer broadly rewrites sections and suppresses warnings. Its
formatters may use missing-data sentinels; old geometry helpers have limited
dimensionality/type handling. Historical demo tests reference absent APIs and
are retained outside the active modern test suite.

The new editor checks finite SWMM numeric syntax, supported engineering bounds,
IDs, node/link references, required cross sections, instruction conflicts, and
preconditions. DEPTH offsets are nonnegative relative heights; ELEVATION offsets
are signed absolute elevations and may use `*`. Cross-section diameters use
length units, not flow units or GIS inches. FORCE_MAIN Geom2 depends on the
selected friction equation and is not conduit Manning roughness.

Within the narrow `Change` API, renames, deletion, endpoint rewiring, shape conversion, other cross-section
shapes, complete loading/control dependencies, and unit/datum conversion are
deferred and fail explicitly when requested. Nonempty unknown/vendor cards or
unresolved abbreviated headers block hydraulic edits. Unchanged supported-but-
deferred cards are preserved, without a claim of full validation. Effective
initial-depth/crown checks and complete model validity require engine review.

The selected format reference and optional check are EPA SWMM 5.2.4; compatibility
with other builds or vendor dialects is not established. Two-file publication
is not a filesystem-wide transaction: an interrupted process can leave a
candidate without its audit. Consumers must require the completion audit and
verify its candidate hash.

`shmm/tests/data/base.inp` and the template in `shmm/utils.py` contain historical
dummy records/settings. They are retained for characterization, not selected as
Oregon City's baseline or production creation templates.

Open production specification items are `STUB_TARGET_ENGINE`, `STUB_OREGON_CITY_BASELINE`,
`STUB_FINISHED_DATA_CONTRACT`, `STUB_CREATION_TEMPLATE`, and
`STUB_BACKEND_AND_DRIVERS`. Their meaning and effect are documented in the
specification. The coverage matrix also documents explicit section/dependency
stubs. They are missing functionality, not successful placeholder operations.

### Prepared acceptance fixtures and manual review

`tests/fixtures/network/` contains the coordinated prepared baseline INP,
rebuilt `updates.gdb`, matching portable `updates.json.gz`, scope/hold inventory,
and separate existing/future instruction sets. The baseline has 263 conduits,
263 junctions, four pumps, three storage nodes, and one weir. Fixture preparation,
anonymization tools, raw exports, private crosswalks, and privacy comparisons
are maintained outside SHMM and are not included in its commits.

The scoped inventory has 310 candidate pipes: 309 currently included across
both scenarios (239 priority 1 and 70 priority 2), plus one excluded record.
Another 243 full-network candidates are outside the prepared subnetwork scope.
Fourteen reviewed diameter-only patches have exact target/endpoint associations;
they are independently checked against supplied diameters in inches divided
by 12 to obtain feet. Other fields remain held for engineering completion.

The existing acceptance case adds one explicitly synthetic pipe and supporting
node; the future case adds two. Those additions test the generic addition
contract and are not finished project instructions. The reviewed diameter
patches currently agree between scenarios; separate tests retain that distinction.

All source asset IDs and map geometry were replaced before delivery. Display
geometry is synthetic, has no geographic CRS, and must not supply hydraulic
lengths or elevations. External rainfall was unavailable and was replaced by
synthetic inline zero rainfall. These fixtures are not hydraulically equivalent
to the source event. Retained topology and exact hydraulic values can still
fingerprint a source; no stronger anonymity certification is claimed.

Manual QA/QC should inspect:

- The distinction between reviewed patches, synthetic additions, exclusions,
  and unresolved field holds in the fixture README and workload inventory.
- Candidate endpoints, cross sections, dimensions, offset mode, and native units.
- Audit fields and hashes, including source keys and the explicit engine status.
- Retention of pumps, storage, DWF, RDII, inflows, patterns, curves, and event settings.
- Engine warnings and continuity results; input acceptance is not calibration.

## Developer README

### Repository structure

- `shmm/inp.py`: legacy model wrapper and section writing.
- `shmm/editing.py`: explicit edit planning, preview, validation, publication, audit.
- `shmm/engine.py`: optional explicitly selected/pinned engine check.
- `shmm/shmm.py`: template loader.
- `shmm/gis.py`: map-geometry table helpers.
- `shmm/utils.py`: section formatters and embedded template.
- `shmm/tests/`: historical tests and fixtures.
- `tests/`: active modern preservation, editing, fixture, and engine tests.
- `examples/edit_fixture.py`: editable VS Code example; no required CLI.
- `docs/`: Sphinx documentation and modernization specification.
- `pyproject.toml`: Python 3.12 packaging and active pytest configuration.
- `requirements_dev.txt`, `tox.ini`, `.travis.yml`: historical setup references;
  their obsolete versions are not the modern installation workflow.

### Environment and execution

Use Python 3.12 in a dedicated environment and select its interpreter in VS Code.
With the updated hymo checkout beside SHMM, create `.venv` using
`python -m venv .venv` from a Python 3.12 interpreter. On Windows, install both
checkouts with `.venv/Scripts/python.exe -m pip install -e ../hymo -e ".[test]"`.
SHMM 0.1.1 requires hymo >=0.2.1, which provides the document/schema interface
and ordered interior-vertex reader;
installing an older published hymo is insufficient. Publication to PyPI is not
part of this change. GIS extras are optional; the core editor has no ArcGIS
dependency. Existing hymo table/report readers retain their pandas dependency.

Verification used Python 3.12.13, pytest 9.1.1, pandas 3.0.6, and NumPy 2.5.4.
These are tested versions, not a complete lockfile or a guarantee for all future
dependency releases.
The [verification record](docs/verification.md) records test counts, packaging
checks, prepared-input QA and engine observations for this increment.

Do not use `Make_env.bat` to establish the new environment: it removes an
existing named environment and creates an old Python 3.6 setup. Keep ArcGIS
export/reconciliation workflows separate from the SHMM runtime.

The library interface is primary. Read with `hymo.read_document`, construct
`shmm.Change` records, preview with `shmm.preview_changes`, and apply in memory
with `shmm.apply_changes`. Use `shmm.edit_model` with explicit source/candidate/
audit paths for publication. Edit `SCENARIO` and `REVIEWED_ONLY` in
`examples/edit_fixture.py`, then run that file in VS Code to exercise a prepared
case. Outputs go to `.cache/fixture_demo/<scenario>_<UTC run ID>/candidate.inp`
and `audit.json`; source fixtures remain unchanged. `DEBUG` controls example
logging and defaults to false.

For finished map polylines, construct `shmm.VertexChange(object_id, vertices,
source_key)` and pass a sequence as `vertex_changes=` to the same library
operations. Each geometry audit row contains the ordered before/after points;
the original baseline hash and final candidate hash cover hydraulic and map
edits together. `hymo.read_vertices` handles ordered geometry reading.
`tests/test_geometry.py` checks order, untouched vertex bytes, same-batch
references, invalid coordinates, atomic failure, and publication readback.

`shmm.engine.check_engine` requires explicit executable/library paths, an expected
EPA version integer, and an existing output directory. It verifies both version
sources, retains report/binary artifacts, parses report errors independently of
the executable return code, and checks input nonmutation. Its returned record
contains a pass/failure result and artifact hashes. Engine artifacts are separate
from the application audit, whose engine status remains `not run`.

### Tests, diagnostics, and maintenance

Run `.venv/Scripts/python.exe -m pytest tests -q` from SHMM. In restricted
environments, supply a writable `--basetemp .cache/pytest-run-<unique ID>`.
Never reuse a basetemp containing files you need: pytest manages its contents.
The active suite covers byte preservation, partial edits, additions, preconditions,
invalid values, dependency checks, transaction failures, realistic prepared
fixtures, and newer-card lexical preservation.

Engine tests opt in through `SWMM_ENGINE` (EPA executable path) and `SWMM_LIBRARY`
(solver library path), pinned to version integer 52004. Without these explicit
settings, engine integration tests skip with a reason; mock-based engine failure
tests still run. The baseline, existing, and future prepared models have distinct
engine checks. No continuity acceptance threshold is invented.
The rebuilt FileGDB is versioned in the repository for GIS inspection; ordinary
tests and source distributions use its portable counterpart. Ignore temporary
FileGDB lock files when reviewing commits.

The pinned 5.2.4 checks accepted the prepared baseline and both candidate
scenarios. All three reports retain warning 09 (synthetic rainfall interval)
and warning 02 (an inherited node's maximum depth is increased by the engine).
Flow-routing continuity errors were -0.495%, -0.228%, and -0.050% respectively.
These are recorded observations under synthetic zero rainfall, not supplied
project acceptance tolerances or proof of hydraulic equivalence.

Run hymo's own tests from its checkout with the same environment; its full suite
also checks legacy reader behavior. Historical SHMM demo tests remain available
for reference under `shmm/tests/`, but are not a modern acceptance gate.

The modern path uses module logging and explicit errors without global warning
suppression. Do not import the legacy writer to perform new edits. Extension
work starts with a hymo schema/reading contract, then SHMM validation, editing,
preservation and engine tests before changing the coverage matrix. Full GIS
comparison reports, modern CI, and formatting/linting configuration remain
planned; no claim of those features is made.

Use the GitHub profile for author-contact attribution in new files. Package
authors have names only; project contact links are in `project.urls`. The legacy
`shmm.__email__` attribute is empty and `shmm.__contact__` provides the GitHub
profile. Repository-local Git identity uses a GitHub noreply address for commits.

Preserve the BSD license and useful history. The package originated from
[Cookiecutter](https://github.com/cookiecutter/cookiecutter) and its
[Python package template](https://github.com/audreyr/cookiecutter-pypackage).

