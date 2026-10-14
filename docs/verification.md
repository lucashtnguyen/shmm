# Modernization verification record

- Author: Lucas HT Nguyen
- Contact: [GitHub profile](https://github.com/lucashtnguyen)
- Date: 2026-10-14
- Last modified by: Lucas HT Nguyen
- Maintenance: manually recorded evidence, not an automatically updated badge.

## Summary

### Preview and written-model diff increment (2026-10-14)

SHMM 0.1.2 adds standalone JSON/CSV/filterable HTML comparisons before and after
publication. The upstream umdev handoff carries finished instructions and source
evidence; SHMM compares actual effects and independently reconstructs the expected
candidate for exact-byte verification. This checks preservation rather than
engineering acceptance. See [handoff contract](umdev_handoff.md).

The full Python 3.12 suite passed **172 tests**, with **five optional engine
checks skipped** because executable/library variables were not set. The 27 new
synthetic cases cover unrequested parameter/comment/header/whitespace/card changes,
missing requests, repeated curves and DWF rows, ordered/repeated vertices,
baseline-only assets, no-ops, opaque tails, malformed candidate rows, source
evidence, safe HTML/CSV and non-overwriting report publication. The diff increment
does not change model hydraulics or rerun EPA engine validation.

Earlier verification records below describe their corresponding increments.

The first increment establishes the hymo reading/SHMM editing boundary and
separate existing/future acceptance cases. It does not apply all candidate
priority records. Fourteen individually reviewed diameter patches are executable
in each scenario. One existing and two future synthetic additions exercise the
addition contract. Other project fields remain engineering holds.

### Automated verification

- SHMM full suite: **114 passed**, with the installed EPA 5.2.4 engine explicitly
  enabled. This includes baseline, existing and future model compatibility
  checks, plus valid/invalid small engine examples.
- A subsequent prepared-GDB QA-report contract test increased the active suite
  to **115 distinct checks**. The updated seven-test fixture module passed.
  Other implementation/tests were unchanged after the full run.
- hymo full suite: **68 passed, one existing skip**. The legacy column-schema
  comparison is skipped because those schemas vary by SWMM version. Thirty
  new reading/schema tests passed within that suite.
- Environment: Python 3.12.13, pytest 9.1.1, pandas 3.0.6, NumPy 2.5.4.
- Editable local installs succeeded: hymo 0.2.0 and SHMM 0.1.0.
- SHMM source archive and Python 3 wheel builds succeeded. Wheel metadata has
  Python >=3.12 and hymo >=0.2.0; modern modules are present and private fixture
  preparation tools are absent. FileGDB is repository-only; portable fixtures
  are included in the source archive.
- The edit-and-run example published separate candidate/audit files for both
  scenarios and verified candidate agreement with preview.

### Add-only link geometry increment

SHMM 0.1.1 adds ordered interior XY through a separate `VertexChange` contract
in the existing preview/apply/publication transaction. hymo >=0.2.1 reads those
rows; SHMM retains the original baseline hash and final combined candidate hash.
Synthetic tests verify input order, same-batch references and coordinates,
preservation of legacy repeated-ID vertex rows, finite values, straight links,
readback, and failure without publication. Hydraulic lengths and elevations are
never inferred from display geometry.

The updated full SHMM suite passed **145 tests**, with five explicit optional
engine checks skipped because their executable/library variables were not set.
The geometry increment did not rerun hydraulic engine validation. Diff
whitespace checks passed. SHMM 0.1.1 wheel/source builds passed; wheel metadata
requires hymo >=0.2.1 and the geometry module is packaged. Source-archive checks
confirmed the geometry tests are included and local `.chi`/`.db` files excluded.
Original fixture/engine results above remain the earlier verification evidence.

### Prepared input QA/QC

External preparation verified 360,540 replacement-identity fields,
1,797,370 geodatabase attributes, and 15,330 synthetic geometry comparisons.
No errors were found. Hydraulic attribute readback was exact. ArcGIS's
unknown-CRS coordinate storage introduced a maximum display XY difference of
0.0001220703125 ft, within an explicitly documented 0.001-ft tolerance.
Private source hashes confirmed original model and geodatabase data were
unchanged, excluding transient lock files. Private hashes, original identifiers,
and source paths are not included here.

The public [QA report](../tests/fixtures/network/gdb_verification.json) records
counts and scope only. Ordinary tests check neutral identifiers, synthetic local
geometry, consistent model/GIS endpoints, approved field associations,
independent expected diameters, additions, untouched sections and stale inputs.
Preparation, crosswalks, and original-source comparisons remain outside SHMM.

### Engine observations and manual review

Executable and library version were both verified as **52004**. The prepared
baseline and both candidates completed without detected solver errors.
All three retained warning 09 (synthetic rainfall interval) and warning 02
(the engine increases an inherited node's maximum depth). Flow-routing
continuity errors were -0.495%, -0.228%, and -0.050% for baseline, existing,
and future respectively. No project acceptance tolerance was supplied or inferred.

Review audit hashes and before/after values, endpoint connectivity, dimensions,
offset interpretation, loading/control preservation, unresolved scope holds,
and engine warnings. Engine acceptance does not establish calibration.
Unavailable external rainfall was replaced with synthetic inline zero rainfall;
these runs do not establish equivalence to the original event.

Asset identifiers and original spatial locations were removed. Retained topology
and hydraulic values can fingerprint a source; no absolute anonymity guarantee
or external-release certification is made.

## Developer README

Run `python -m pytest tests -q` using the dedicated SHMM environment. Optional
real engine checks require explicit `SWMM_ENGINE` and `SWMM_LIBRARY` settings;
without them, five integration cases skip while mock engine tests still run.
Use a new writable `--basetemp` in restricted environments. The full run used
`.cache/pytest-final`; engine reports and binary files remain in its per-test
directories for local inspection. They are ignored by Git.

Run hymo's tests from its checkout using the same environment. Build SHMM with
`python -m build --no-isolation` after installing build tooling. The Windows
sandbox denied some temporary-file/metadata operations; using workspace staging
and an authorized build escalation resolved those environment restrictions.
No failed test or source-validity check was bypassed.

This record describes one tested reference build. See the
[coverage matrix](swmm_section_coverage.md) for deferred section contracts and
the [fixture README](../tests/fixtures/network/README.md) for scenario expectations.
