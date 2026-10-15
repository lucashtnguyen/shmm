# umdev to SHMM handoff and manual model QA

- Author: Lucas HT Nguyen
- Last modified by: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-15
- Status: Implemented comparison API; upstream envelope fields are a versioned contract.

## Summary

umdev prepares finished model values from utility GIS and engineering evidence.
It owns schema mapping, asset/port matching, unit and datum reconciliation,
scenario selection, roughness policies, assumptions, unresolved holds and
engineering QA. hymo reads model documents. SHMM applies finished instructions,
preserves other model text, and produces two manual QA comparisons:

1. **Preview:** compare baseline with the proposed in-memory candidate before
   publication. Report requested operations, no-ops, field values and geometry,
   source references, upstream assignment basis and QA flags.
2. **Written-model comparison:** read the actual published candidate with hymo.
   Compare it with baseline and independently replay the same supplied requests.
   Verify exact expected bytes, not only an operation count or audit assertion.

The baseline hash guards against stale preparation. The preview candidate hash
identifies what was reviewed; the written candidate hash identifies what was
published. A different written hash is a failed preservation/reconciliation
check, even when differences affect only comments or numeric spelling.
Passing this check establishes faithful model editing, not hydraulic or datum
acceptance. Review upstream QA flags and resulting profiles separately.

umdev also compares candidate topology against the baseline. Its component and
directed-route reports distinguish inherited independent basins from new pipe
islands, and retain held or excluded exact-ID connector evidence. Those reports
belong alongside both SHMM comparisons in the review package. A possible connector
does not authorize scope expansion or make its unresolved parameters usable.
Existing storage can be referenced by finished gravity-conduit instructions while
its storage profile, curves, coordinates and controls remain preserved. SHMM does
not derive those endpoint parameters or resolve station/force-main representation.

### Handoff contract

The project orchestrator passes one scenario per handoff envelope. Required
envelope fields are `schema_version: "1"`, `baseline_sha256`, `scenario`,
`changes`, `vertex_changes`, and `evidence`. Reproducibility metadata includes
`prepared_hash`, `config_hash` and `source_manifest`; these describe upstream
preparation and remain in its run manifest rather than being inferred by SHMM.

- Each `changes` entry supplies the existing `Change` constructor fields:
  `action`, `section`, `object_id`, `values`, `source_key`, and optional
  `expected` old values and `comment`. The optional comment is nonempty printable
  single-line text for **new JUNCTIONS only**, written literally after ` ; `;
  newline/control characters and update annotations are rejected. Existing
  comments are preserved. Only currently implemented add/update sections are
  accepted. Missing assets never imply deletion.
- Each `vertex_changes` entry supplies `VertexChange`: `object_id`, ordered
  interior `vertices` XY pairs, `source_key`, and optional `action: "add"`.
  Geometry is already in the baseline map coordinate system. It does not
  establish pipe length, invert elevation or flow direction.
- `evidence` maps instruction `source_key` to JSON metadata. Include source
  observations/references, assignment basis, QA flags, category and units as
  applicable. SHMM preserves these fields in JSON, CSV and HTML without
  interpreting raw GIS or overriding upstream decisions.
- Values use baseline field units and offset convention. Upstream must resolve
  the units, datum and engineering assignment before creating instructions.
  Held or unresolved assets remain in upstream reports instead of being
  converted to zero-valued model edits.

An explicitly authorized missing-rim policy can hand off `max_depth=12.345`
plus `comment="UMDEV_PLACEHOLDER_RIM MaxDepth=12.345 ft"` (or `m` for SI).
This is a visible unresolved-data marker, not a surveyed rim. The literal native
depth is unchanged by `LINK_OFFSETS ELEVATION`. The caller supplies its QA flag,
assumption and source evidence; SHMM does not derive or approve the placeholder.

Keep the immutable operation sequence and evidence for all three stages:
preview, publication, and independent written-model comparison. Changing
instructions after preview requires a fresh preview and review identity.

### What the comparisons show

The JSON report contains baseline/candidate/expected hashes, requested operations
(including no-ops), actual effects, missing expected effects, field units,
source keys/evidence, section matching strategies and full raw text differences.
Supported JUNCTIONS, CONDUITS, XSECTIONS and COORDINATES use unique ASCII
case-insensitive IDs and hymo named-field schemas. Documented optional defaults
are compared as values. Numeric-equivalent spellings are semantically equal;
exact-byte reconciliation still detects unrequested reformatting.
Junction inline annotations have an explicit `comment` effect and retain their
instruction source keys and evidence. The requested comment also appears in the
edit audit and requested-operation record. Missing or changed published comment
text fails reconciliation, even when all hydraulic fields match.

VERTICES compare complete ordered coordinate-token sequences per link, preserving
repeated rows and bends. Other sections—including curves, timeseries, controls
and vendor cards—use ordered complete lexical rows. Repeated identifiers are
never collapsed. Unsupported row changes are reported as removal/addition
occurrences with source line references; they are not given invented field
names or semantic pairings. Malformed/duplicate supported records fall back to
lexical comparison for diagnosis. Opaque tails, comments, section headers,
record order and whitespace remain visible in the raw text diff and are
covered by exact expected-byte checks.

CSV and standalone HTML include requested/no-op, observed and missing effects.
HTML can filter IDs, fields, source keys and upstream QA flags. All untrusted
text is escaped, and CSV formula-leading values are emitted as text. JSON
retains original values. Reports do not need an external web service.

### Manual review

- Confirm the baseline, scenario, source/config manifest and candidate hashes.
- Review additions and field changes with their source basis, units and QA flags.
- Review all missing/unexpected effects and raw text differences; require
  `verification.matches_expected` before accepting publication integrity.
- Inspect the candidate in a model viewer for connectivity, profiles, offsets,
  rims, cross sections and geometry. Review upstream engineering holds.
- Treat simulation, calibration and engineering acceptance as separate checks.

No interactive map/profile renderer is implemented in this increment. The tables,
raw text and model viewer provide manual review. Lexical comparison covers
all cards but does not imply complete semantic understanding of every SWMM card.

## Developer README

`shmm.preview_model_diff(document, changes, vertex_changes=(), evidence=None,
expected_hash=None)` returns `ModelDiff(candidate_data, report)` without files.
`shmm.edit_model` remains the preserving publisher. Read its actual output with
`hymo.read_document`, then call `shmm.compare_written_model(baseline, candidate,
changes, vertex_changes=(), evidence=None, expected_hash=None)`.

`shmm.write_diff_reports(diff, existing_output_directory, prefix="preview_diff")`
writes `.json`, `.csv` and `.html` and returns their paths. Use another prefix
such as `written_model_diff` for readback. Existing targets cannot be overwritten.
Report publication errors remove files created by that call; an external
interruption can leave a partial set, so consumers must require all three files.
The report schema version is `"1"`. `verification.matches_expected` is the
acceptance predicate for exact requested model effects. The existing editing
audit remains the publication completion record.

Tests: `python -m pytest tests/test_comparison.py`. The active full suite uses
`python -m pytest`; EPA engine checks remain explicitly opt-in. Tests use
synthetic networks, repeated cards, comments, unrequested/missing changes,
ordered vertices, no-ops, evidence escaping and publication collisions.
