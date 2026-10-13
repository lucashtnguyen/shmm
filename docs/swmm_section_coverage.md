# SWMM section coverage and reading contract

- Author: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-13
- Maintenance: manually maintained alongside hymo reading and SHMM editing tests.

## Summary

The supplied integration model does not define the complete SWMM format. The
new document reader retains every section, while the initial SHMM editor
supports a deliberately smaller set of explicit additions and field updates.
Preserving a record is not the same as understanding it or proving that a
solver accepts it. No claim of complete SWMM 5.x support is made.

### Authoritative format baseline

The reference baseline is **EPA SWMM 5.2.4**, not an unspecified "latest 5.x".
EPA lists that build with its 2023-08-07 software and source downloads on the
[official SWMM download page](https://www.epa.gov/water-research/storm-water-management-model-swmm).
Field descriptions and input conventions come from Appendix D of the
[EPA SWMM 5.2 User's Manual](https://www.epa.gov/system/files/documents/2022-04/swmm-users-manual-version-5.2.pdf).

The section inventory below follows the pinned solver's
[section keyword dictionary](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/keywords.c)
and its [text definitions](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/text.h).
Canonical full spellings are used in this document. The solver recognizes
several abbreviated prefixes; retaining a spelling does not imply that the
editor resolves every abbreviation. The deprecated `GW_FLOW` macro exists
in `text.h` but is absent from this build's section keyword array. Treat it as
legacy preserved text, not certified 5.2.4 syntax.

### Meaning of coverage levels

- **Lexed:** section boundaries, records, original lines, and token positions
  are available from hymo. This applies to recognized and unknown sections.
- **Interpreted:** named fields are understood by the initial SHMM operation
  contract; values remain in the model's field units.
- **Checked:** the specific structural checks described here are implemented;
  this does not mean complete EPA grammar or hydraulic validation.
- **Editable:** explicit additions and partial updates are supported through
  SHMM. Renaming, deletion, endpoint rewiring, and object/shape conversion are
  outside the initial contract.
- **Preserved:** unrelated original text is retained. Deferred sections cannot
  be directly edited through the initial operation contract.

### Section matrix

Every row is lexed and preserved. `Deferred` means field interpretation and
direct editing are deferred. The four editable rows are the initial scope;
the remaining rows describe preservation or narrow dependency inspection only.
The stub column points to concrete follow-up work below.

| Section | Interpretation / checks | Direct edit | Deferred work |
| --- | --- | --- | --- |
| TITLE | Raw text | No | TEXT_METADATA |
| OPTIONS | Selected unit/offset settings | No | OPTIONS |
| FILES | Deferred | No | EXTERNAL_FILES |
| RAINGAGES | Deferred | No | CLIMATE |
| TEMPERATURE | Deferred | No | CLIMATE |
| EVAPORATION | Deferred | No | CLIMATE |
| SUBCATCHMENTS | Deferred | No | RUNOFF |
| SUBAREAS | Deferred | No | RUNOFF |
| INFILTRATION | Deferred | No | RUNOFF |
| AQUIFERS | Deferred | No | GROUNDWATER |
| GROUNDWATER | Deferred | No | GROUNDWATER |
| SNOWPACKS | Deferred | No | CLIMATE |
| JUNCTIONS | Named fields, finite values, identity | Add/update | NODE_VARIANTS |
| OUTFALLS | Node identity only | No | NODE_VARIANTS |
| STORAGE | Node identity only | No | NODE_VARIANTS |
| DIVIDERS | Node identity only | No | NODE_VARIANTS |
| CONDUITS | Named fields, endpoints, identity | Add/update | TOPOLOGY |
| PUMPS | Link identity only | No | LINK_VARIANTS |
| ORIFICES | Link identity only | No | LINK_VARIANTS |
| WEIRS | Link identity only | No | LINK_VARIANTS |
| OUTLETS | Link identity only | No | LINK_VARIANTS |
| XSECTIONS | Circular/force-main conduit fields and link | Add/update | XSECTION_VARIANTS |
| TRANSECTS | Deferred | No | XSECTION_VARIANTS |
| LOSSES | Link reference only | No | LINK_VARIANTS |
| CONTROLS | Raw ordered rule text | No | CONTROLS |
| POLLUTANTS | Deferred | No | QUALITY |
| LANDUSES | Deferred | No | QUALITY |
| BUILDUP | Deferred | No | QUALITY |
| WASHOFF | Deferred | No | QUALITY |
| COVERAGES | Deferred | No | QUALITY |
| INFLOWS | Node reference only | No | LOADING |
| DWF | Node reference only | No | LOADING |
| PATTERNS | Deferred | No | LOADING |
| RDII | Node reference only | No | LOADING |
| HYDROGRAPHS | Deferred | No | LOADING |
| LOADINGS | Deferred | No | QUALITY |
| TREATMENT | Raw expression text | No | QUALITY |
| CURVES | Deferred | No | TABLES |
| TIMESERIES | Deferred | No | TABLES |
| REPORT | Deferred | No | OPTIONS |
| COORDINATES | Named fields, finite XY, node | Add/update | MAP_GEOMETRY |
| VERTICES | Link reference; raw ordered records | No | MAP_GEOMETRY |
| POLYGONS | Raw ordered records | No | MAP_GEOMETRY |
| LABELS | Raw text | No | TEXT_METADATA |
| SYMBOLS | Deferred | No | MAP_GEOMETRY |
| BACKDROP | Deferred | No | EXTERNAL_FILES |
| TAGS | Raw text | No | TEXT_METADATA |
| PROFILES | Deferred | No | MAP_GEOMETRY |
| MAP | Deferred | No | MAP_GEOMETRY |
| LID_CONTROLS | Raw repeated records | No | LID |
| LID_USAGE | Deferred | No | LID |
| GWF | Raw expression text | No | GROUNDWATER |
| ADJUSTMENTS | Deferred | No | CLIMATE |
| EVENTS | Raw ordered records | No | EVENTS |
| STREETS | Deferred | No | STREET_INLETS |
| INLET_USAGE | Deferred | No | STREET_INLETS |
| INLETS | Raw repeated records | No | STREET_INLETS |

Unknown/vendor sections are retained by the reader but have no known field
schema or dependency contract. An edit that cannot be assessed safely must
produce a diagnostic. The initial editor blocks hydraulic edits when nonempty
unknown sections are present. Coordinate-only operations and byte-preserving
no-op operations remain available. EPA abbreviated section headers are not
resolved to canonical names yet and therefore trigger the same hydraulic-edit
gate. Absence from this inventory does not authorize dropping
the section. Existing legacy DataFrame properties are separate from this matrix
and do not establish support in the new editor.

### Engineering interpretation and review

The initial operations change supplied values; they do not calculate new
hydraulic parameters. `FLOW_UNITS` determines the accompanying unit system.
Do not assume that the model uses SI units. Offsets require the selected
`LINK_OFFSETS` interpretation, and geographic map lengths do not replace
hydraulic conduit lengths.

Conduit and cross-section parsing must follow the actual optional fields and
shape-dependent formats. Numeric elevations may be negative. In elevation
offset mode, `*` is a valid conduit-offset sentinel; depth offsets have a
different meaning. Custom, irregular, and street sections refer to other
objects rather than using the same fixed numeric layout as circular pipes.
These distinctions are visible in the pinned
[EPA link parser](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/link.c).

For circular pipes, the governing geometry check is diameter greater than
zero; fields 2 through 4 are unused. A force-main roughness parameter must
be positive and its interpretation depends on the force-main equation:
Hazen-Williams coefficient versus Darcy-Weisbach roughness height. It is not
the conduit Manning coefficient. The pinned
[EPA cross-section implementation](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/xsect.c)
and link validation are the basis for these distinctions.

A reviewer should inspect exact before/after values, node references,
cross-section dimensions, offset mode, units, and retained loading/control
records. Solver acceptance and continuity results require a separate pinned
engine run; document-level checks cannot establish calibrated hydraulic
equivalence.

## Developer README

### Library boundary and lossless reader contract

`hymo.document.SWMMDocument` owns reading and lexical interpretation.
SHMM owns edit instructions, field validation, candidate modification,
serialization, readback, publication, and audits. The reader must not acquire
file-writing or mutation methods merely to simplify SHMM.

The document representation should provide:

- Original bytes or an exact reversible text representation, including
  encoding, byte-order mark, mixed line endings, and final-newline state.
- Ordered original lines, section occurrences, one-based source locations,
  token text and character spans, and comments separately from values.
- Read-only record collections; repeated keys are retained, not overwritten.
- Explicit distinction between absent, empty, and unsupported sections.
- Case-insensitive section lookup without changing original spelling.
- Diagnostics for malformed headers and quoting without silently discarding
  lines. Numeric-looking IDs remain strings.

The initial reader exposes zero-based line indices; human-facing diagnostics
convert those to one-based line numbers. It rejects repeated section headers
because the initial editor addresses one section by name. Repeated records
within a section are retained. Original comments remain in source lines; they
are not yet exposed as separate typed comment objects.

Object IDs are matched case-insensitively within their EPA object namespace.
The pinned [EPA hash implementation](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/hash.c)
folds ASCII `a` through `z`; general Unicode case folding is broader than the
solver's behavior and must not silently merge distinct non-ASCII IDs.
Original spelling is retained in the document and audit.

Named field interpretation belongs to hymo as that library's coverage grows.
SHMM's initial field-position contract is limited to editable records and does
not replace comprehensive hymo parsing. Add new typed readers incrementally,
with their own format contracts and test fixtures, while retaining lexical
access for every section.

The legacy hymo reader was inspected as a reference. It reads through text
mode and pandas tables, drops comments for interpreted blocks, and truncates
storage/divider rows to a subset of columns. Its advertised properties include
unimplemented sections and formats inferred from one sample. Those tables
cannot serve as a lossless writing contract.

### Version-specific supplements

The official [EPA release notes](https://github.com/USEPA/Stormwater-Management-Model/releases)
identify important syntax beyond an older sanitary-sewer example: SWMM 5.2.0
introduced streets/inlets, variable-speed pump support, analytic storage
shapes, and control variables/expressions. These must be retained in synthetic
fixtures even before interpretation is implemented. Later 5.2 builds also
changed validations and warning behavior, so a successful run against one
build is not evidence of compatibility with every 5.x release.

The pinned [EPA input reader history](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/input.c)
also records 5.1 additions for climate adjustments, hydraulic events, and
per-subcatchment infiltration methods. Parsing infiltration using only one
fixed Green-Ampt layout is therefore insufficient.

The initial numeric contract accepts ASCII decimal/exponent quantities, not
Python-specific underscore or Unicode-digit spellings. Integral barrel and
culvert fields require special care because EPA reads them using `atoi`;
writing an exponent such as `1e1` would produce 1 rather than 10. The barrel
count is stored as a C `char` in the pinned
[EPA object definitions](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/objects.h),
so a portable editor bounds it to 1 through 127. Culvert codes outside 1 through
57 do not activate inlet control; zero explicitly means none, following
[EPA culvert logic](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/solver/culvert.c).

### Optional pinned engine check

`shmm.engine.check_engine` takes explicit input, executable, solver-library,
version, and output-directory arguments. It queries both executable and
library versions, runs with the input parent as its working directory, retains
reports/results separately, and verifies that source bytes remain unchanged.
The output directory must exist and matching report/result names must not
already exist. `EngineCheck.passed` requires process success, no detected report
errors, and a nonempty report/result. Warnings remain available for review.

The [EPA executable wrapper](https://github.com/USEPA/Stormwater-Management-Model/blob/v5.2.4/src/run/main.c)
returns zero even after model errors, so exit status alone is insufficient.
Failed-model reports are retained and reported through `EngineCheck.errors`.
Version/configuration errors and timeouts raise; incomplete staged files are
discarded. No engine installation or download is implicit.

`tests/test_engine.py` verifies the runner using mocks. Two optional real-engine
cases run only when `SWMM_ENGINE` and `SWMM_LIBRARY` explicitly identify a
5.2.4 installation in the test environment. One synthetic DWF model must pass;
another with an undefined endpoint must fail. These cases are skipped on hosts
without opt-in tools. Zero-rainfall or arbitrary synthetic loading establishes
compatibility only; it does not reproduce the source model's event or hydraulics.

### Deferred contracts and explicit stubs

These are documented deferred contracts, not executable implementations that
pretend to succeed. Each marker uses the required project stub convention.

- TODO: STUB_TEXT_METADATA — field semantics and escaping for descriptions,
  tags, labels, and titles need dedicated interpretation and privacy tests.
- TODO: STUB_OPTIONS — complete option/report grammar and version-dependent
  defaults are not yet implemented; preserve supplied settings.
- TODO: STUB_EXTERNAL_FILES — portable handling and validation of referenced
  files, backdrops, and relative paths require a caller-owned resource contract.
- TODO: STUB_CLIMATE — climate, rain-gage, snow, and adjustment variants require
  typed readers and fixtures beyond the initial sewer-network scenario.
- TODO: STUB_RUNOFF — runoff and infiltration methods need variant-specific
  field contracts and subcatchment dependency validation.
- TODO: STUB_GROUNDWATER — aquifers, groundwater, and expressions need typed
  parsing and verified object references.
- TODO: STUB_NODE_VARIANTS — outfalls, dividers, and every storage variant need
  full fields and dependencies before direct edits are supported.
- TODO: STUB_TOPOLOGY — renames, deletions, endpoint rewiring, and load transfers
  need dependency-complete operations; they are not inferred from GIS proximity.
- TODO: STUB_LINK_VARIANTS — pumps, regulators, outlets, and losses require
  their own variant-specific edit and validation contracts.
- TODO: STUB_XSECTION_VARIANTS — other shapes, curves, transects, street
  references, and conversions require dedicated geometry/dependency checks.
- TODO: STUB_CONTROLS — rule syntax, variables, expressions, and referenced
  objects require a grammar before dependency-changing edits are allowed.
- TODO: STUB_QUALITY — pollutants, land uses, buildup/washoff, loadings, and
  treatment expressions require linked contracts and numerical checks.
- TODO: STUB_LOADING — complete DWF, inflow, RDII, pattern, and hydrograph
  interpretation requires continuation and optional-field fixtures.
- TODO: STUB_TABLES — time-series/curve continuations, file references, curve
  types, and ordering constraints require comprehensive parsing.
- TODO: STUB_MAP_GEOMETRY — vertices, polygons, symbols, map bounds, profiles,
  coordinate metadata, and replacement geometry need explicit contracts.
- TODO: STUB_LID — multi-record LID controls and usage variants need typed
  readers and dependencies before direct edits are supported.
- TODO: STUB_EVENTS — event-window semantics and date validation need focused
  tests; existing records remain unchanged.
- TODO: STUB_STREET_INLETS — streets, inlet designs/usages, and capture-curve
  dependencies need 5.2-specific typed readers and edit tests.
- TODO: STUB_ENGINE_MATRIX — supported solver builds and numerical acceptance
  criteria must be established separately from syntax/reference checks.
- TODO: STUB_OPAQUE_DEPENDENCIES — unknown/vendor sections and abbreviated EPA
  headers need explicit dependency/alias contracts before hydraulic edits.

### Test and extension checklist

The independent synthetic test suite should establish byte-identical no-op
writing and unchanged spans after targeted edits. Include comments, omitted
optional fields, empty/absent sections, repeated IDs in multi-record sections,
leading whitespace, mixed case, quoted file names, numeric-looking IDs,
malformed tokens, and LF/CRLF/byte-order-mark input. Existing unknown fields
must never disappear through a fixed-column DataFrame conversion.

`tests/fixtures/swmm52_supplement.inp` provides illustrative newer syntax and
an intentional unknown section. `tests/test_swmm52_supplement.py` verifies
retained numeric-looking IDs, sentinel offsets, repeated inlet and table
records, expressions, quoted paths, and exact original bytes under mixed
newlines. Run these tests through `python -m pytest
tests/test_swmm52_supplement.py`; install the companion hymo checkout in the
chosen environment first. The fixture is not a simulation benchmark.

Add synthetic preservation examples for street/inlet records, analytic
storage, pump-5 curves, control expressions, groundwater expressions, all
infiltration methods, LID controls, table continuations, and hydraulic events.
Preservation fixtures are lexical tests unless explicitly verified with the
pinned solver. Do not present illustrative tokens as hydraulically valid
models.

For each future section, add a hymo reader test, a SHMM edit/preservation test,
invalid-input cases, and reference checks before changing its matrix status.
Expected output values must be independently specified. Keep project-specific
matching, datum decisions, and review priorities outside these contracts.
