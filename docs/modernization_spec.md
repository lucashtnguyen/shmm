# SHMM modernization specification

- Author: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-15
- Last modified by: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-15

Status: Draft v0.3 for implementation planning. Manually maintained.

Implementation note (2026-10-13): the initial preserving reading/editing
foundation now exists. hymo 0.2.1 owns immutable document reading, four named
section schemas, and ordered interior-vertex reading; SHMM 0.1.2 owns explicit
add/update instructions, add-only link vertices, previews, candidate writing,
readback, audits and optional pinned EPA 5.2.4 checks. The
broader GIS ingestion and dependency-complete operation requirements
below remain the target design. Repository findings describe the pre-change
legacy implementation. See the [current README](../README.md) and
[section coverage matrix](swmm_section_coverage.md) for implemented scope.

Implementation note (2026-10-14): SHMM now implements both a preview comparison
and an independent written-model comparison. Structured JSON, CSV and standalone
filterable HTML show requests/no-ops, actual effects, missing/unexpected effects,
source evidence, QA flags and model hashes. Exact-byte reconciliation includes
opaque source text. Interactive map/profile rendering remains deferred.
See the [umdev handoff contract](umdev_handoff.md) for implemented APIs and
comparison strategies; all-section lexical coverage is not a claim of complete
SWMM semantic interpretation.

## Summary

### umdev handoff and two-stage manual QA

umdev owns configurable utility GIS interpretation and engineering preparation.
It supplies scenario-specific finished operations and evidence; SHMM owns
comparison, safe application, preservation and written-model verification.
Project configuration, source data, crosswalks and engineering decisions remain
outside the public SHMM and umdev repos.

The handoff envelope identifies schema version, baseline SHA-256, scenario,
serialized `Change` and `VertexChange` sequences, evidence keyed by `source_key`,
and upstream prepared/config/source-manifest identities. SHMM receives finished
values in baseline units and coordinates. Unresolved assets are upstream holds,
not zero defaults or implicit deletions.

Implemented pressure handoff (2026-10-15): umdev can supply new conduit records
with `XSECTIONS.shape=FORCE_MAIN`, explicit diameter and positive `geom2`, and
separate conduit Manning `roughness`. `geom2` means dimensionless Hazen-Williams
C under `H-W`, or Darcy-Weisbach roughness height in inches for US flow units
and millimetres for SI flow units under `D-W`. The existing baseline options
govern the meaning; SHMM does not select or convert the equation. Touched
force-main conduits/cross sections require `DYNWAVE` and a supported equation;
absent options use EPA defaults `DYNWAVE` and `H-W`. Untouched inherited pressure
records are preserved without broadening unrelated edits into engine validation.

umdev supplies role-specific junction `surcharge_depth` instructions, including
999 model length units for a reviewed sealed pressure connection. Open receiving
manholes and wet wells require their own explicit roles and retain their reviewed
representation. SHMM writes finished junction values; it does not infer sealing
from GIS connectivity, set storage surcharge, fabricate node profiles, or create
pump curves/controls. Evidence must identify role, units, coefficient basis, and
provisional assumptions. Both review diffs must expose these requested effects.
The surcharge allowance is additional head above maximum depth before flooding,
not an established pressure rating. Missing upstream parameters remain holds.

Implemented visible annotation handoff (2026-10-15): an optional `Change.comment`
contains finished printable single-line text for a newly added JUNCTIONS record.
SHMM appends it after the inline comment delimiter, verifies it on readback, and
retains it in the audit and the preview/written-model `comment` effects with the
instruction's evidence. Newlines, control characters, empty comments, annotations
on updates and annotations on other card types are rejected. Existing inline
comments remain untouched. Annotation text never supplies hydraulic field values.

For example, a caller-approved missing-rim placeholder can supply literal
`max_depth=12.345` and `UMDEV_PLACEHOLDER_RIM MaxDepth=12.345 ft` (or `m` for SI)
as its separate comment. Maximum depth stays a depth in native model length units
under both DEPTH and ELEVATION conduit-offset conventions. The writer does not
derive a fictitious absolute rim or approve the placeholder; umdev retains the
missing-rim QA basis and the project decides whether to include that node. Any
unrequested annotation mutation fails written-model reconciliation.

Before publication, generate a **preview diff** comparing baseline to the
proposed candidate, including old/new values and units, ordered geometry,
source basis, QA flags and no-op requests. After publication, re-read the
actual file with hymo and generate a **written-model diff** using the same
immutable baseline, requests and evidence. Compare all actual effects against
independently replayed instructions and require exact expected bytes. Include
both baseline/candidate hashes and expected candidate hash in the report.

Use unique named-field matching only for verified schemas. Preserve repeated
ordered rows such as VERTICES; use explicit lexical row comparison for deferred
cards rather than silently dropping or collapsing them. Full text and exact
byte comparisons cover opaque tails, comments, whitespace, headers and order.
Missing requested effects and unrequested effects fail reconciliation, including
opaque text changes. JSON, CSV and filterable HTML support manual QA; future
map/profile renderers extend these reports. Upstream engineering QA and optional
simulation remain distinct from faithful edit verification.

### Purpose and boundary

SHMM takes **finished, model-ready data** and applies it to a new or existing
SWMM `.inp` model. It supports GIS/model comparison so users can inspect what
will change, then assembles or edits the model. Resolving asset associations,
source conflicts, and engineering decisions belongs to upstream workflows. Oregon City is the
first intended application, not the source of project rules embedded in SHMM.

The end goal supports three workflows:

1. **Compare:** compare finished GIS/table records with a selected model using
   supplied object IDs or an explicit crosswalk; show differences and proposed
   edits without writing a model. This is also a standalone workflow.
2. **Create:** assemble a new model from explicit settings and finished node,
   link, loading, catchment, and geometry records.
3. **Modify:** apply explicit additions, updates, deletions, and geometry
   replacements to a selected baseline, preserving unrelated content.

Shapefiles and other geospatial formats are sources of finished records.
Reading a layer does not authorize parameter inference or source-data repair.

| Responsibility | Upstream workflow | SHMM |
| --- | --- | --- |
| Authoritative inputs | Select model/GIS versions | Load explicitly supplied inputs |
| GIS/model comparison | Supply finished values and explicit asset associations; explain engineering causes | Show baseline/GIS values, differences, and which edits will be applied |
| Asset matching and aggregation | Resolve identities, branches, splits, and merges | Apply finished IDs and connectivity |
| Existing/future conditions | Resolve lifecycle, horizon, and replacements | Apply supplied scenario-specific records |
| Elevations | Attribute ports, verify datum/units, resolve conflicts | Validate compatibility and serialize final values |
| Model parameters | Determine lengths, offsets, depths, roughness, areas, and loads | Validate and write supplied values |
| Map geometry | Supply intended CRS and object associations | Convert supported finished geometry into INP map records |
| Engineering review | Finish decisions and supply explicit edits | Preview, apply, and record instructions |
| File integrity | Provide engineering evidence | Check syntax, references, preservation, and readback |
| Simulation/calibration | Select events and performance criteria | Optional engine compatibility check |

**Excluded:** raw GIS cleanup, nearest-neighbor matching, snapping, endpoint
inference, reach aggregation, eligibility rules, datum conversion, survey
interpretation, interpolation, parameter estimation, project review-tracker
management, I&I analysis, and automatic scenario selection.
SHMM does not translate unfinished review statuses into model edits.

Comparison and change-review tables, reports, and optional map layers are within
SHMM's scope. Inferring matches or deciding how to resolve a discrepancy is
upstream. A reported GIS/model difference does not automatically become an edit.

Validation remains a SHMM responsibility: inconsistent finished data must not
produce a corrupt model. SHMM reports the problem; upstream resolves the
engineering decision. It must not silently fill required values with `-999`,
zero, guessed parameters, or undocumented defaults.

### Repository findings

Retain the original section-table editing concept and map-geometry helpers.
Modernize their contracts and implementation before production use.

| Files | Observed condition | Required response |
| --- | --- | --- |
| `shmm/inp.py` | Depends on `hymo.SWMMInpFile`; globally suppresses warnings; discovers tables by introspection; broadly rewrites sections | Explicit section support and diagnostics; preserve untouched text |
| `shmm/gis.py` | Uses `DataFrame.append`; lines assume three coordinates; limited polygon handling | Finished-geometry conversion with dimensionality/order checks |
| `shmm/utils.py` | Missing-data sentinels; embedded dummy template, fixed settings/dates, placeholder path | Validate required fields; provide versioned modern templates |
| `shmm/tests/data/base.inp` | 2018 dates, dummy IDs, CFS/KINWAVE/DEPTH settings | Retain as legacy fixture; add separate valid modern examples |
| `shmm/tests/`, `shmm/__init__.py` | Tests reference absent demo/validate/viz APIs; runtime imports test helper | Replace demo tests with model-contract coverage; separate test dependencies |
| Packaging, tox, Travis, `Make_env.bat` | Old interpreter/tool versions; environment script removes an existing environment | Reproducible Python 3.12 packaging/setup without deleting environments |
| `README.md` | Useful intent, template-loader typo, obsolete append examples | Correct legacy description and document planned boundary |

These findings come from source inspection, not a passing runtime assessment.
No package, model, or GIS behavior is changed by this specification.

### Oregon City crosswalk

The following were inspected read-only in the separate Oregon City workspace.
Paths are relative to that workspace and identify evidence, not SHMM schemas.

| Evidence | Integration consequence |
| --- | --- |
| `model_gis_comparison/README.md` and `config.json` | Size/pump scope, aggregation, and lifecycle rules remain upstream |
| `model_gis_comparison/discovery/20261006_assessment/README.md` | Refreshed GIS identities and per-endpoint datum evidence must be resolved upstream |
| `model_gis_comparison/update_outputs/20261007T170615_222969Z/README.md` | Explained differences are not completed edits; unresolved invert holds must not become instructions automatically |
| `model_model_comparison/README.md` | Preserve inherited RDII/DWF, curves, controls, and event settings unless explicitly targeted |
| Chats `Plan model GIS comparison workflow` and `Compare Oregon City model topology` | Project context supports the boundary; finished records and selected snapshots govern application |

The current GIS comparison configuration identifies
`Aggregated_Model_2026-09-01.inp` as its baseline. The separate model comparison
uses `Basin8_10_RDII_recalib_2025.inp` and
`South_Ex_Eval_PDXII_5yr_sealed.inp`. SHMM must receive an explicitly selected
baseline rather than choose among them.

A project-owned exporter should produce finished scenario records and explicit
edit operations, including finalized split/merge topology and load transfers.
SHMM compares that export with the selected baseline, shows proposed changes,
and applies the explicit operation set. No Oregon City diameter cutoff, pump exception,
datum assumption, or review-status vocabulary belongs in the generic package.
The existing tracker and JSON exports are not assumed to be model-ready inputs.

### Workflow, outputs, and human QA/QC

1. Upstream finishes model values, identities, scenario selection, and geometry.
2. The caller supplies a baseline or creation template, finished records,
   metadata, and explicit operations when creating or modifying a model.
3. SHMM validates comparability, produces the GIS/model comparison, and
   previews exact proposed edits. Compare-only runs stop here.
4. SHMM applies the operation set to an in-memory candidate, validates
   dependencies, writes a staged file, and reads it back.
5. A successful application publishes a separate candidate INP and application
   audit, with a baseline-to-candidate comparison confirming the actual edits.
6. The project engineer reviews the candidate and any hydraulic results.
   Promotion to a project baseline remains outside SHMM.

Comparison returns structured results and can save a human-readable HTML report
and CSV change table. A preview includes proposed edits/findings without creating
a candidate. Application produces a candidate `.inp` and JSON audit. Optional
engine checking produces an engine report and, when requested, binary results.
Output paths are caller inputs; source models must not be overwritten. GIS
change-review map layers may be exported when valid geometry/CRS is supplied.
These are comparison products; project issue trackers and decision registers
remain upstream.

### GIS/model comparison and change review

The user should be able to load finished GIS/table data and a model, see their
differences, inspect which changes are in the supplied operation set, and then
apply that set. Comparison does not require an edit set. It uses exact final
model IDs or a supplied crosswalk; spatial proximity is not a matching rule.
An aggregated asset association needs finished model-level values upstream;
SHMM does not calculate a representative diameter or combine source lengths.

The comparison must distinguish:

- Objects with comparable supplied values: changed or unchanged, with model
  value, GIS/proposed value, units, and field-level differences.
- Source-only and model-only objects: present on one side of the declared
  comparison scope. Absence from a partial export never implies deletion.
- Missing/ambiguous associations, unsupported fields, or incompatible
  units/datum/CRS: explicitly not comparable, with the reason.
- Differences included in explicit operations versus differences only reported.
  List explicit deletions even when no GIS feature exists for the deleted object.
- Hydraulic attributes/connectivity versus display-geometry changes. Show
  affected references and dependencies for additions, deletions, and updates.

Each row must carry object type/ID, section/field, source key, association,
baseline value, supplied value, comparison status, and planned operation if any.
For comparable numeric values, define delta as **supplied minus baseline**;
for application verification, use **candidate minus baseline**. Label the basis
and units. The existing Oregon City register's Model-minus-GIS convention must
not be carried over silently.

Only explicitly supplied fields are compared. Normalize supported numeric
spellings and documented engine defaults without discarding the original
representations. Record-order differences are ignored only for unordered
sections; vertex, polygon, curve, and continuation order remains meaningful.
Do not compare elevation deltas across incompatible datums or geometry across
incompatible CRSs. Comparison can still report other valid fields on the object.

Show exact differences by default. Optional caller-defined tolerances can
classify significance, but must not hide requested edits or change their values.
A small difference can still be an intended edit. Do not introduce project
screening thresholds into the generic package.

The review report should show counts and filterable detail for adds, updates,
deletes, unchanged records, differences outside the operation set, and
not-comparable records. Optional maps show baseline and proposed geometry with
stable links to detail rows; attribute-only edits may use retained baseline
geometry. Nonspatial changes must remain visible in the table/report.

Preview and application must use the same validated inputs and operation set.
Re-read the candidate and compare it with the baseline to verify that every
actual edit was requested and every requested effect is represented. Record
no-op instructions explicitly. A refreshed input or changed operation set
requires a refreshed preview. This is input-consistency checking, not a separate
permission mechanism.

Reviewers should compare applied changes with upstream instructions, inspect
IDs, connectivity, offsets, dimensions, and map geometry in the intended SWMM
interface, and verify that unrelated loads, controls, curves, and events were
retained. File validity does not establish hydraulic adequacy or calibration.
In the comparison report, inspect differences outside the operation set and
not-comparable rows; the report does not certify unresolved source data.

## Developer README

### Environment and design direction

- Python 3.12 in a dedicated environment, confirmed on 2026-10-13.
- Callable Python library and edit-and-run VS Code workflow are primary; an
  optional CLI can follow later.
- Keep `shmm` and its useful section-table interface concept. Use `Path`, type
  hints, NumPy-style docstrings, explicit exceptions, and module logging.
- Modernize packaging through `pyproject.toml`; separate runtime, development,
  and optional engine-check dependencies. Do not import tests at runtime.
- GeoPandas-based finished-data readers are proposed, subject to Python 3.12
  compatibility and driver checks. ArcPy is not a core dependency; upstream
  may export finished tables from an ArcGIS environment.
- Evaluate retaining/replacing `hymo` through preservation tests before
  selecting a backend. No unverified new backend API is prescribed here.
- Use pytest, formatting/linting, and Windows Python 3.12 CI. Dependency/tool
  versions must be verified during implementation, not copied from old pins.

### Finished-input contract

This is a proposed contract, not an implemented API/configuration schema.
Finalize exact names and types with the first upstream adapters.

| Input | Required information |
| --- | --- |
| Target | Compare/create/modify workflow, comparison scope, baseline/template, engine/dialect; output path for application |
| Source identity | Dataset/layer/table identity, stable source record key, available snapshot hashes |
| Object identity | Final SWMM ID, object type, section-specific record key; IDs remain strings |
| Comparison associations | Exact shared model IDs or an explicit crosswalk, selected fields, and declared full-snapshot/partial-export scope |
| Values | Complete records for additions; explicit fields/values for patches |
| Operations | Required for application: add, update, delete, or replace a named object's map geometry; optional in compare-only mode |
| Units/spatial basis | Target flow units, dimensional field units, map CRS, vertical-datum compatibility for elevation edits |
| Preconditions | Expected baseline hash and old values of touched fields |
| Creation settings | Explicit options and required boundary/loading definitions, directly supplied or in a versioned template |

First-release values must already use the target SWMM field units and geometry
the declared map CRS. SHMM does not reproject, convert datums, or derive hydraulic
values. A field named `diameter` does not prove its units or its shape-specific
meaning. Configured column mapping is allowed; engineering transformation is
upstream. Preserve source keys through ingestion.

Accept finished in-memory tables/GeoDataFrames and a documented table exchange
format. Initial geospatial readers should support shapefile and GeoPackage.
Other formats, including File Geodatabase, follow through optional adapters
after driver verification. Select layers explicitly. Account for shapefile
sidecars and shortened field names. No driver availability is promised yet.

Updates are partial patches: omitted fields remain unchanged. Null does not
mean clear a field; clearing an optional value must be explicit and valid.
Additions require complete valid records. Distinguish creation snapshots from
edit sets. Do not infer deletions from absent rows or use implicit upserts.

Not all sections have one row per object. Vertices/polygons require ordered
points; curves, patterns, loading, and hydrographs require section-specific
compound keys/continuation handling. Repeated object IDs are legal where the
section contract allows them. Validate unique keys at the correct granularity.

### Functional requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| F-01 | Read supported INPs with original text/source locations | Legacy/modern fixtures load; malformed records have contextual diagnostics |
| F-02 | Preserve untouched text, comments, and unknown sections | Byte-identical no-op; targeted edits leave untouched spans unchanged |
| F-03 | Add records and patch explicit fields | Happy path; missing-target rejection; unspecified values retained |
| F-04 | Delete explicitly named records/objects only | No dangling references; no automatic cascade or inferred deletion |
| F-05 | Create from finished records and explicit settings | Modern synthetic example accepted by the selected engine |
| F-06 | Read finished spatial data and write map geometry | 2D/3D tests, point order, line endpoints, polygon exterior handling |
| F-07 | Validate schemas, units, keys, and dependencies | Invalid input fails with source/target context |
| F-08 | Preview without candidate publication | Exact adds, old/new values, deletes, affected references |
| F-09 | Audit actual applied changes | Candidate agrees with audit; no unrequested changes |
| F-10 | Reject stale preconditions | Unexpected baseline/old values cannot silently receive a patch |
| F-11 | Read back staged output before publication | Validation/failure tests; source inputs unchanged |
| F-12 | Optional pinned-engine check | Version/result recorded; skipped check explicit |
| F-13 | Standalone GIS/model comparison using supplied associations | Read-only report of changed/unchanged, source-only/model-only, and not-comparable records |
| F-14 | Human-readable review of differences and explicit proposed edits | Filterable report/CSV distinguishes reported differences from operations and includes nonspatial changes |
| F-15 | Verify baseline-to-candidate changes against the previewed operation set | Requested effects and actual edits agree; unrequested changes fail verification |

Byte preservation is a backend selection gate. A library that normalizes the
whole file needs a preserving document layer or a different backend. Unchanged
unknown sections can pass through, but dependency-sensitive edits must be
blocked if their references cannot be handled safely. Preserved does not mean
validated. Renames and object-type conversions are deferred until reference
handling is implemented.

### Section coverage and engineering interpretation

Maintain an explicit matrix of **preserved**, **parsed/validated**, and
**editable** sections for each release:

1. Foundation: title/options, junctions/outfalls, conduits/cross sections,
   coordinates/vertices, and relevant display records.
2. Oregon City readiness: storage, pumps, curves, losses, controls, DWF,
   inflows, patterns, RDII, and hydrographs. Preserve these from the foundation
   stage; dependency support must precede network changes that affect them.
3. Runoff creation: rain gages, subcatchments, subareas, infiltration, polygons,
   and their supplied parameters/references.
4. Other specialized sections follow actual project needs and fixtures.

Unsupported edits fail explicitly. Do not drop optional tails, unknown fields,
comments, or continuation records.

- Respect `FLOW_UNITS`, `LINK_OFFSETS`, routing/infiltration methods, and
  shape-dependent meanings. Option changes that reinterpret inherited values
  require compatible supplied replacements; no automatic whole-model conversion.
- DEPTH conduit offsets are relative to node inverts; ELEVATION offsets are
  absolute elevations. Upstream supplies final offsets. SHMM checks interpretation.
- Node maximum depth is a depth, not a rim elevation. SHMM does not choose a
  controlling port or compute depth from rim minus invert.
- GIS Z does not automatically become a hydraulic elevation. Map records use
  XY; any omitted Z receives explicit treatment in the audit.
- A GIS force-main label does not select SWMM shape, friction equation,
  roughness, pump curve, or controls. Those choices must be supplied.
- Require finite values and section-specific legal ranges. Use engine defaults
  only where explicitly supported and documented.
- Use verified engine identity rules while preserving ID spelling/leading zeros.
  Reject conflicting operations and duplicate unique keys.
- Validate endpoints, cross sections, curves, load associations, and other
  required dependencies. Do not redistribute loads or cascade deletions.
- Replace geometry per named object and preserve supplied point order. Handle
  line endpoints using SWMM map semantics; do not reverse connectivity because
  a line was digitized in the opposite direction.
- Initial conversion supports nonempty points, single LineStrings, and simple
  polygon exteriors. Reject invalid, multipart, curved, holed, or ambiguous
  geometry. Upstream may supply an explicitly selected valid map outline.
- Geometry is optional when no map is required. Unknown/incompatible CRS blocks
  geometry application, not unrelated nonspatial inspection.
- Report unusual values/adverse grades without correcting them. Distinguish
  structural errors from engineering plausibility findings.
- Preserve SWMM-required input date syntax. Use ISO-8601 for audit metadata,
  not as an automatic replacement for native model dates.

Format basis: [EPA SWMM 5.2 User's Manual, Appendix D](https://www.epa.gov/system/files/documents/2022-04/swmm-users-manual-version-5.2.pdf).
The [EPA download page](https://www.epa.gov/water-research/storm-water-management-model-swmm)
and [official solver release](https://github.com/USEPA/Stormwater-Management-Model/releases/tag/v5.2.4)
checked on 2026-10-13 identify 5.2.4. That is a planning reference build;
Oregon City's actual engine/vendor dialect remains to be confirmed.

### Architecture and reliability

Use focused components inside the existing package: preserving INP I/O,
section schemas, finished-data readers, comparison/change reporting, operation
application, validation, and audit output. Keep geospatial reading separate from model editing and engine
execution optional. Do not add a project reconciliation engine or review database.

Audit mode, input/template/source hashes, source keys, package/schema versions,
engine/dialect, units/CRS/datum declarations, requested/applied operations,
old/new values, validation findings, output hash/path, and engine-check status.
Every applied edit must trace to its finished source record and instruction.
Record comparison scope, associations, selected fields, tolerances, and preview
fingerprints. Before/after verification must use the same section semantics as
the preview; readback must verify the written file, not just the in-memory model.

Apply each operation set as one transaction. Invalid/conflicting operations
prevent publication rather than silently applying a subset. Upstream may supply
an intentionally smaller finished edit set. Stage output separately, re-read
it, and use a completion record so an interrupted publication cannot appear
successful. Recheck input fingerprints before publication. Output ordering and
numeric serialization must be deterministic without material precision loss.

### Tests

| Group | Required cases |
| --- | --- |
| Preservation | No-op bytes, targeted edits, unknown sections/comments, quoted tokens, literal paths, CRLF/LF, supported encodings, optional tails |
| Operations | Add/update/delete, partial patches, explicit clears, missing targets, conflicting keys, stale hash/values, repeated application without duplicates |
| Finished inputs | Missing/nonfinite fields, string IDs, units/datum/CRS mismatches, layer selection, source tracing |
| Comparison | Standalone read-only use, exact IDs/crosswalks, ambiguous keys, source-only/model-only objects, partial export without inferred deletion, incompatible datums/CRSs, numeric spelling/default equivalence, sequence order |
| Change review | Differences outside edit set, explicit deletions, no-op instructions, delta sign/units, tolerances do not hide requested edits, nonspatial rows, preview/apply consistency, detection of unrequested candidate changes |
| Geometry | 2D/3D, bends/order/endpoints, unsupported geometry rejection, geometry-only edits leave hydraulic values unchanged |
| Quantitative contracts | US/metric inputs, diameter vs cross-section units, DEPTH/ELEVATION interpretation, bounds, numeric precision |
| Dependencies | RDII/DWF, controls, curves/patterns, explicit deletion/split replacements without lost/duplicated supplied loading |
| Reliability | Source preservation, readback, deterministic output, failed writes, audit completeness, output/source path collision |
| Engine | Synthetic creation, no-op baseline, controlled edit, pinned error/warning capture, explicit skipped status |

Hand-checked examples test interpretation of supplied offsets/units; they do
not introduce parameter derivation into SHMM. Hydraulic regression comparisons
use the same engine and forcing. Project acceptance tolerances must be supplied.

### Implementation sequence

1. **Preservation foundation:** characterize legacy behavior; modernize Python
   3.12 packaging; select backend and schemas. Exit: no-op and targeted-edit
   tests pass.
2. **Comparison and finished-data modification:** implement standalone comparison,
   change reports, contracts, preconditions, operations, geometry replacement,
   validation, and audit. Exit: a synthetic edit set previews and applies exactly
   or fails as a whole; before/after comparison confirms the edits without
   altering sources. Compare-only use must work without an operation set.
3. **Oregon City integration:** upstream exports a small finished edit set and
   selected baseline; extend dependency support as needed. Exit: requested
   edits are traced, inherited content retained, candidate engine-accepted.
   Outstanding GIS/datum decisions remain upstream work.
4. **New-model creation:** add versioned templates and valid synthetic network
   and runoff examples. Exit: finished data produce valid models without
   dummy required records, invented values, or external machine-specific paths.

Keep historical fixtures until regression coverage permits retirement. Updating
dates alone does not modernize a model. Client models remain local integration
fixtures unless redistribution is separately authorized.

### Open decisions and stubs

- `STUB_TARGET_ENGINE`: confirm engine build/vendor extensions and supported range.
- `STUB_OREGON_CITY_BASELINE`: select modification baseline and identify external
  dependencies and its map CRS/elevation basis.
- `STUB_FINISHED_DATA_CONTRACT`: agree exchange format, field mappings, compound
  keys, explicit comparison crosswalk/scope, and operation envelope with the
  upstream exporter.
- `STUB_CREATION_TEMPLATE`: choose explicit first-release model options and
  required boundary/loading definitions.
- `STUB_BACKEND_AND_DRIVERS`: verify Python 3.12 backend/dependencies,
  preservation behavior, and optional spatial drivers before pinning.

These are missing design/integration decisions, not implemented placeholder
behavior. They block affected production operations, not independent I/O work.
This draft changes documentation only; code, model, and GIS files remain as found.
