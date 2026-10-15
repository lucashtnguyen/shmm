# Spatial model QA export

- Author: Lucas HT Nguyen
- Contact: https://github.com/lucashtnguyen
- Date: 2026-10-15
- Manually maintained implementation contract.

## Summary

The exporter writes a GIS review copy of the actual INP network. Model values,
source evidence and topology remain separate: a map line is not a calculated
hydraulic result, and SHMM does not resolve source measurements or select a
Manning coefficient. Upstream workflows supply finished assumptions and flags.

The bundle contains two shapefiles (`nodes`, `links`), each with `.shp`, `.shx`,
`.dbf`, `.prj` and UTF-8 `.cpg`; `manifest.json`; full `qa_features.json` evidence;
`components.json` with complete node/link lists; and `components.csv` / `islands.csv`
for tabular symbology and review. All records are retained. Assets lacking XY
have null shapes and explicit geometry flags, which must be inspected in the
attribute table because they cannot appear on the map.

### GIS fields

| Field | Meaning |
| --- | --- |
| MODEL_ID / SECTION | Actual identifier and SWMM family; node/link namespaces remain separate. |
| QA_KEY | Unique stable within-namespace join to complete per-feature evidence. |
| FROM_NODE / TO_NODE | Written link endpoints and nominal direction. |
| COMP_ID | Deterministic weak component ID for this exact network. |
| ISLAND_ID | Unique ID for a new unsupported component, including an isolated new node. |
| IS_ISLAND | 1 new component with no baseline node or declared outfall; 0 anchored/supported; -1 unresolved without baseline. |
| BASE_NODE | 1 when a node exists in the baseline; 0 otherwise, including link records. |
| NO_OUTLET | 1 when a node, or a link's downstream node, lacks a nominal directed outfall route. |
| GEOM_OK | 1 valid map geometry; 0 null geometry with a diagnostic flag. |
| QA_COVER | Caller asserts partial/complete provenance, or unknown when none was supplied. |
| ASSUMED | 1 supplied assumption or placeholder; 0 no such supplied flag; -1 no annotation. |
| PLACEHOLDR | 1 supplied placeholder; 0 no supplied placeholder; -1 no annotation. |
| PROVISION | 1 supplied provisional evidence; 0 none supplied; -1 no annotation. |
| QA_COUNT / QA_FLAGS | Unique flag count and a short display summary. |
| QA_TRUNC | 1 when the summary exceeds 254 UTF-8 bytes; full details remain in JSON. |
| INV_ELEV / MAX_DEPTH / SUR_DEPTH | Native model elevations, maximum depths and junction surcharge depths where applicable. |
| LENGTH / ROUGHNESS | Native conduit length and CONDUITS roughness field, without conversion. |
| IN_OFFSET / OUT_OFFSET | Written conduit offsets, governed by LINK_OFFSETS. |
| XS_SHAPE / GEOM1 / GEOM2 | Supplied cross-section values; their meaning depends on shape and model options. XS_SHAPE avoids ArcGIS's reserved Shape geometry field. |

Every distinct flag additionally receives a stable ten-character integer DBF
field: five readable characters plus a hash suffix. The manifest maps full
flag names to these fields. A flag value of 1 means it was supplied or produced
as an export geometry diagnostic; 0 means it was not supplied for that feature.
Flags on partial or unknown provenance are not an inventory of every historical
assumption. A placeholder is an assumption; a provisional datum remains separately
visible. Full JSON retains each affected field, basis and source evidence, even
when the same flag applies to several parameters on one object.

All hydraulic values use the INP conventions. A maximum depth of 12.345 remains
a depth even with LINK_OFFSETS=ELEVATION. A FORCE_MAIN GEOM2 may be a dimensionless
Hazen-Williams C or a Darcy-Weisbach roughness height in inches/millimetres;
CONDUITS roughness remains a separate field. Read the retained model options
before interpreting these attributes. `.prj` establishes XY map coordinates,
not hydraulic vertical datum or the units of every model field.

### Island interpretation

Every declared node and all CONDUITS, PUMPS, WEIRS, ORIFICES and OUTLETS
participate in weak-component analysis. An explicit original baseline protects
independent legitimate basins regardless of their size. A new component with a
declared outfall is a terminal network rather than an unsupported island.
Without a baseline, an unanchored component's inherited/new status is unknown.

IDs are deterministic under card reordering, but may change after topology
changes. Always keep the manifest hash and component membership together;
these are run identifiers, not permanent asset identities. `NO_OUTLET` follows
nominal link direction and is independent of weak component attachment. It
does not evaluate controls, pump operation, reverse flow, capacity or calibration.

### Manual QA

1. Load both shapefiles in the stated CRS. Check model hash and export counts.
2. Symbolize components by COMP_ID or new islands by ISLAND_ID. Filter
   IS_ISLAND=1 for the unsupported-island layer; use islands.csv for the list.
3. Select PLACEHOLDR=1, ASSUMED=1 and PROVISION=1 separately, then inspect
   individual flag columns and full field-specific evidence through QA_KEY.
4. Inspect unknown/partial provenance and GEOM_OK=0. Null shapes remain counted.
5. Review the baseline-to-preview and baseline-to-written-model diffs alongside
   source measurements, node profiles and engineering holds. The export contains
   written assets only; held/excluded proposals remain upstream review records.

Known limits: network points and polylines only; no subcatchment polygons, 3D
geometry, reprojection, geographic anonymization, parameter inference, or hydraulic
simulation. DBF numeric fields use nine decimal places; exact original values
and tokens remain in the JSON evidence. Very long IDs, numeric overflow, excessive
flag fields or field-name collisions fail explicitly instead of losing information.

## Developer README

Install the GIS extra. `shmm.export_shapefiles(document, output_directory,
crs=..., baseline=None, annotations=(), annotation_model_sha256=None)` returns a
manifest and publishes a new directory after verifying all shape records, XY,
flags, CRS and counts. It never overwrites an existing destination.

Construct `GISFlag(code, category, field='', basis='', evidence={})`, with category
assumption, placeholder, provisional or qa. Group these into
`GISAnnotation(family, object_id, flags=(), coverage='partial', source_key='')`.
Family is node or link; IDs match ASCII case-insensitively. Multiple parameter
flags belong in a single annotation per object. Annotation evidence must be JSON
serializable. Supplying any annotations requires the SHA-256 of the exact model
document; missing/stale hashes, unknown IDs and duplicate annotations fail.

Baseline comparison and geometry reading use hymo's immutable documents and
lexical records. No dependency on UMDEV or project GIS is introduced. The caller
owns the join from upstream evidence to actual written IDs, filters out holds and
unapplied alternatives, and preserves the source-evidence hashes. The orchestrator
should call this after successful written-model reconciliation and retain the
bundle with that run. Re-export after regeneration to a new directory.

Focused tests: `python -m pytest tests/test_spatial.py`. Full tests:
`python -m pytest`. GIS tests skip when optional dependencies are absent.

Format/API references: [PyShp](https://github.com/GeospatialPython/pyshp) and
[pyproj CRS](https://pyproj4.github.io/pyproj/stable/api/crs/crs.html).
