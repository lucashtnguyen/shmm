"""Export actual SWMM network geometry and supplied QA evidence for GIS review.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-15
Manually maintained. No parameter inference, reprojection or model editing.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field as dataclass_field
from hashlib import sha256
import csv
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import time
from typing import Any, Mapping, Sequence

from hymo import SWMMDocument
from hymo.geometry import read_vertices
from hymo.schemas import interpret_fields

from .editing import LINK_SECTIONS, NODE_SECTIONS, NUMBER_PATTERN, _key


@dataclass(frozen=True)
class GISFlag:
    """One caller-supplied, field-specific assumption or QA finding.

    Parameters
    ----------
    code : str
        Stable flag name; also receives an individual integer DBF field.
    category : str
        ``assumption``, ``placeholder``, ``provisional`` or ``qa``.
    field : str, optional
        Model parameter affected by this flag.
    basis : str, optional
        Human-readable engineering basis.
    evidence : mapping, optional
        Full JSON evidence, preserved without DBF truncation in the sidecar.
    """

    code: str
    category: str
    field: str = ""
    basis: str = ""
    evidence: Mapping[str, Any] = dataclass_field(default_factory=dict)


@dataclass(frozen=True)
class GISAnnotation:
    """Finished upstream QA evidence for one exact model object.

    Parameters
    ----------
    family : str
        ``node`` or ``link``; their identifier namespaces are separate.
    object_id : str
        Actual written model identity, matched ASCII case-insensitively.
    flags : sequence of GISFlag
        All supplied assumptions, placeholders and QA findings for this object.
    coverage : str, optional
        ``partial`` (default) or ``complete``. Complete is a caller assertion,
        not an engineering determination by SHMM. Missing annotations are unknown.
    source_key : str, optional
        Stable upstream evidence identity, retained in full JSON.
    """

    family: str
    object_id: str
    flags: Sequence[GISFlag] = ()
    coverage: str = "partial"
    source_key: str = ""


# DBF names are explicit and at most ten ASCII bytes. Full IDs are never truncated.
_FIELDS = (
    ("QA_KEY", "C", 24, 0), ("MODEL_ID", "C", 254, 0),
    ("SECTION", "C", 12, 0), ("FROM_NODE", "C", 254, 0),
    ("TO_NODE", "C", 254, 0), ("COMP_ID", "C", 12, 0),
    ("ISLAND_ID", "C", 12, 0), ("IS_ISLAND", "N", 2, 0),
    ("BASE_NODE", "N", 1, 0), ("NO_OUTLET", "N", 1, 0),
    ("GEOM_OK", "N", 1, 0), ("QA_COVER", "C", 8, 0),
    ("ASSUMED", "N", 2, 0), ("PLACEHOLDR", "N", 2, 0),
    ("PROVISION", "N", 2, 0), ("QA_COUNT", "N", 8, 0),
    ("QA_FLAGS", "C", 254, 0), ("QA_TRUNC", "N", 1, 0),
    ("INV_ELEV", "N", 24, 9), ("MAX_DEPTH", "N", 24, 9),
    ("SUR_DEPTH", "N", 24, 9), ("LENGTH", "N", 24, 9),
    ("ROUGHNESS", "N", 24, 9), ("IN_OFFSET", "N", 24, 9),
    ("OUT_OFFSET", "N", 24, 9), ("XS_SHAPE", "C", 32, 0),
    ("GEOM1", "N", 24, 9), ("GEOM2", "N", 24, 9),
)


def _number(token: str) -> float:
    """Read a finite numeric model value, rejecting nonfinite geometry/attributes."""
    if NUMBER_PATTERN.fullmatch(token) is None:
        raise ValueError(f"Invalid model number: {token}")
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"Nonfinite model value: {token}")
    return value


def _verify(condition: bool, detail: str) -> None:
    """Fail spatial readback explicitly, including when Python assertions are off."""
    if not condition:
        raise ValueError(f"Shapefile readback failed: {detail}")


def _publish_directory(stage: Path, target: Path) -> None:
    """Retry short Windows sharing locks without copying an incomplete bundle.

    Notes
    -----
    Search indexing/virus scanning can briefly hold freshly closed sidecars on
    Windows. Retry only sharing/access errors, for at most 1.55 seconds total;
    persistent permission failures and existing destinations still fail closed.
    """
    delays = (0.05, 0.1, 0.2, 0.4, 0.8)
    for attempt in range(len(delays) + 1):
        if target.exists():
            raise FileExistsError(target)
        try:
            stage.rename(target)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == len(delays):
                raise
            time.sleep(delays[attempt])


def _objects(document: SWMMDocument) -> tuple[dict[str, dict], dict[str, dict]]:
    """Index actual declared assets, rejecting ambiguous or dangling identities."""
    result = []
    for family, sections in (("node", NODE_SECTIONS), ("link", LINK_SECTIONS)):
        objects: dict[str, dict] = {}
        for section in sections:
            for row in document.records(section):
                required = 2 if family == "node" else 3
                if len(row.tokens) < required:
                    raise ValueError(f"Incomplete {section} row at line {row.line_index + 1}")
                identity = row.tokens[0]
                if not identity.strip() or len(identity.encode("utf-8")) > 254:
                    raise ValueError("Model IDs must fit DBF text without truncation")
                key = _key(identity)
                if key in objects:
                    raise ValueError(f"Duplicate {family} identity: {identity}")
                objects[key] = {"object_id": identity, "section": section, "tokens": row.tokens, "record": row}
        result.append(objects)
    nodes, links = result
    for link in links.values():
        if any(_key(end) not in nodes for end in link["tokens"][1:3]):
            raise ValueError(f"Dangling link endpoint: {link['object_id']}")
    return nodes, links


def _geometry(document: SWMMDocument, nodes: Mapping[str, dict],
              links: Mapping[str, dict]) -> tuple[dict, dict]:
    """Read model XY and ordered vertices; missing XY remains null, never guessed."""
    coordinates = {}
    for row in document.records("COORDINATES"):
        key = _key(row.tokens[0])
        if key not in nodes or key in coordinates or len(row.tokens) != 3:
            raise ValueError("Orphan, duplicate or malformed COORDINATES row")
        values = interpret_fields("COORDINATES", row)
        coordinates[key] = (_number(values["x"]), _number(values["y"]))
    for row in document.records("VERTICES"):
        if _key(row.tokens[0]) not in links:
            raise ValueError("Orphan VERTICES row")
    vertices = {key: read_vertices(document, row["object_id"]) for key, row in links.items()}
    return coordinates, vertices


def _components(nodes: Mapping[str, dict], links: Mapping[str, dict],
                baseline: SWMMDocument | None) -> tuple[list[dict], dict, set[str], set[str]]:
    """Report weak components and nominal outlet reachability, retaining all assets."""
    base_nodes, _ = _objects(baseline) if baseline is not None else ({}, {})
    graph: dict[str, set[str]] = {key: set() for key in nodes}
    reverse: dict[str, set[str]] = defaultdict(set)
    for link in links.values():
        start, end = map(_key, link["tokens"][1:3])
        graph[start].add(end)
        graph[end].add(start)
        reverse[end].add(start)
    terminals = {key for key, row in nodes.items() if row["section"] == "OUTFALLS"}
    reachable, pending = set(terminals), deque(sorted(terminals))
    while pending:
        for previous in sorted(reverse[pending.popleft()] - reachable):
            reachable.add(previous)
            pending.append(previous)
    unseen, rows, membership, island_count = set(nodes), [], {}, 0
    while unseen:
        pending_nodes, members = [min(unseen)], set()
        while pending_nodes:
            key = pending_nodes.pop()
            if key in members:
                continue
            members.add(key)
            unseen.discard(key)
            pending_nodes.extend(graph[key] - members)
        identity = f"C{len(rows) + 1:05d}"
        old = members & base_nodes.keys()
        outfalls = members & terminals
        island = not old and not outfalls
        # Without a baseline, an unanchored component could be an intentional
        # inherited basin. Unknown (-1) must not masquerade as reviewed exclusion.
        is_island = int(island) if baseline is not None else (-1 if island else 0)
        if is_island == 1:
            island_count += 1
        component = {"component_id": identity,
                     "island_id": f"I{island_count:05d}" if is_island == 1 else "",
                     "is_island": is_island,
                     "classification": ("baseline_connected" if old else "terminal_network" if outfalls
                                        else "unsupported_island" if baseline is not None else "unanchored_unknown"),
                     "node_ids": [nodes[key]["object_id"] for key in sorted(members)],
                     "link_ids": [], "baseline_node_count": len(old),
                     "terminal_count": len(outfalls),
                     "nodes_without_outlet": len(members - reachable)}
        rows.append(component)
        for key in members:
            membership[key] = component
    for key, link in sorted(links.items()):
        membership[_key(link["tokens"][1])]["link_ids"].append(link["object_id"])
    return rows, membership, set(base_nodes), reachable


def _annotations(annotations: Sequence[GISAnnotation], nodes: Mapping[str, dict],
                 links: Mapping[str, dict]) -> dict[tuple[str, str], GISAnnotation]:
    """Validate exact annotation identities and preserve all supplied JSON evidence."""
    indexed = {}
    for annotation in annotations:
        family = annotation.family
        key = (family, _key(annotation.object_id))
        if family not in {"node", "link"} or key[1] not in (nodes if family == "node" else links):
            raise ValueError(f"Annotation does not identify an actual model asset: {key}")
        if key in indexed or annotation.coverage not in {"partial", "complete"}:
            raise ValueError("Duplicate annotation or invalid provenance coverage")
        for flag in annotation.flags:
            if not flag.code.strip() or flag.category not in {"assumption", "placeholder", "provisional", "qa"}:
                raise ValueError("Flags require a nonempty code and supported category")
            if any(ord(character) < 32 for character in flag.code):
                raise ValueError("Flag codes must be printable")
        json.dumps(asdict(annotation), allow_nan=False)
        indexed[key] = annotation
    return indexed


def _flag_fields(codes: set[str]) -> dict[str, str]:
    """Give each flag a deterministic short DBF name with collision rejection."""
    result = {}
    reserved = {row[0] for row in _FIELDS}
    for code in sorted(codes):
        prefix = re.sub("[^A-Z0-9]", "", code.upper())[:5].ljust(5, "_")
        if not prefix[0].isalpha():
            prefix = "F" + prefix[:4]
        name = prefix + "_" + sha256(code.encode("utf-8")).hexdigest()[:4].upper()
        if name in reserved:
            raise ValueError("Flag field collision; use distinct stable flag codes")
        reserved.add(name)
        result[code] = name
    # Keep a conservative DBF field limit; no supplied flags may disappear.
    if len(result) + len(_FIELDS) > 255:
        raise ValueError("Too many flags for one shapefile; split the reviewed export")
    return result


def _attributes(family: str, key: str, row: Mapping[str, Any], component: Mapping[str, Any],
                annotation: GISAnnotation | None, geometry_flags: list[GISFlag],
                is_baseline: bool, no_outlet: bool) -> tuple[dict, dict]:
    """Prepare DBF symbology fields and full untruncated per-feature evidence."""
    flags = list(annotation.flags) if annotation else []
    flags.extend(geometry_flags)
    codes = sorted({flag.code for flag in flags})
    summary = ";".join(codes)
    preview = summary.encode("utf-8")[:254].decode("utf-8", errors="ignore")
    qa_key = ("N" if family == "node" else "L") + sha256(key.encode("utf-8")).hexdigest()[:20]
    categories = {flag.category for flag in flags}
    coverage = annotation.coverage if annotation else "unknown"
    attrs = dict(QA_KEY=qa_key, MODEL_ID=row["object_id"], SECTION=row["section"],
                 FROM_NODE=row["tokens"][1] if family == "link" else "",
                 TO_NODE=row["tokens"][2] if family == "link" else "",
                 COMP_ID=component["component_id"], ISLAND_ID=component["island_id"],
                 IS_ISLAND=component["is_island"], BASE_NODE=int(is_baseline),
                 NO_OUTLET=int(no_outlet), GEOM_OK=int(not geometry_flags), QA_COVER=coverage,
                 ASSUMED=int(bool(categories & {"assumption", "placeholder"})) if annotation else -1,
                 PLACEHOLDR=int("placeholder" in categories) if annotation else -1,
                 PROVISION=int("provisional" in categories) if annotation else -1,
                 QA_COUNT=len(codes), QA_FLAGS=preview, QA_TRUNC=int(preview != summary))
    full = {"qa_key": qa_key, "family": family, "object_id": row["object_id"],
            "section": row["section"], "component_id": component["component_id"],
            "island_id": component["island_id"], "coverage": coverage,
            "flags": [asdict(flag) for flag in flags],
            "source_key": annotation.source_key if annotation else "",
            "model_tokens": list(row["tokens"])}
    return attrs, full


def export_shapefiles(document: SWMMDocument, output_directory: str | Path, *,
                      crs: Any, baseline: SWMMDocument | None = None,
                      annotations: Sequence[GISAnnotation] = (),
                      annotation_model_sha256: str | None = None) -> dict[str, Any]:
    """Publish a verified node/link shapefile bundle with QA flags and island IDs.

    Parameters
    ----------
    document : SWMMDocument
        Actual written model, read with hymo. Original bytes remain unchanged.
    output_directory : str or Path
        New caller-owned directory. Existing destinations are never overwritten.
    crs : pyproj-compatible CRS input
        Explicit CRS of model map XY; no reprojection or unit inference occurs.
    baseline : SWMMDocument, optional
        Original baseline used to distinguish inherited basins from new islands.
    annotations : sequence of GISAnnotation, optional
        Finished upstream assumption/placeholder/QA evidence for actual assets.
    annotation_model_sha256 : str, optional
        Required exact model hash when supplying annotations; stale evidence fails.

    Returns
    -------
    dict
        Manifest with paths, hashes, counts and schema. Files include nodes.shp,
        links.shp and their sidecars, components.csv, islands.csv and full QA JSON.

    Raises
    ------
    ImportError
        Optional ``pyshp``/``pyproj`` export dependencies are unavailable.
    ValueError
        CRS, identity, coordinates, attributes or evidence are invalid/stale.
    FileExistsError
        The output directory already exists.

    Notes
    -----
    All four node and five link families participate. Missing map coordinates
    produce null shapes and explicit QA flags, not invented XY or dropped assets.
    Nominal direction follows model endpoints. Weak components and outlet paths
    do not establish hydraulic connectivity under surcharge or pump operation.
    Inherited assumptions cannot be reconstructed from numerical values alone.
    No annotation means unknown provenance, never a declaration of clean data.
    Shapefile text is bounded; QA_TRUNC marks summarized flag text. Individual
    flag columns and the QA_KEY join retain all flags in qa_features.json.
    """
    import shapefile
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    target = Path(output_directory).resolve()
    if target.exists():
        raise FileExistsError(target)
    if crs is None:
        raise ValueError("Explicit map CRS is required")
    try:
        projection = CRS.from_user_input(crs)
    except CRSError as error:
        raise ValueError("Invalid explicit map CRS") from error
    if len(projection.axis_info) != 2:
        raise ValueError("Export requires a two-dimensional map CRS")
    model_hash = sha256(document.data).hexdigest()
    if annotations and annotation_model_sha256 != model_hash:
        raise ValueError("Annotation model hash is missing or stale")
    nodes, links = _objects(document)
    coordinates, vertices = _geometry(document, nodes, links)
    components, membership, base_nodes, reachable = _components(nodes, links, baseline)
    annotation_index = _annotations(annotations, nodes, links)
    features: dict[str, list] = {"nodes": [], "links": []}
    cross_sections = {}
    for row in document.records("XSECTIONS"):
        key = _key(row.tokens[0])
        if key not in links or key in cross_sections:
            raise ValueError("Duplicate or orphan cross-section identity")
        cross_sections[key] = interpret_fields("XSECTIONS", row)
    for family, objects in (("node", nodes), ("link", links)):
        for key, row in sorted(objects.items()):
            geometry_flags = []
            if family == "node":
                points = [coordinates[key]] if key in coordinates else None
            else:
                start, end = map(_key, row["tokens"][1:3])
                points = [coordinates[start], *vertices[key], coordinates[end]] if start in coordinates and end in coordinates else None
                if points and len(set(points)) < 2:
                    geometry_flags.append(GISFlag("degenerate_link_geometry", "qa", "geometry"))
                    points = None
            if points is None and not geometry_flags:
                geometry_flags.append(GISFlag("missing_map_coordinates", "qa", "geometry"))
            component = membership[key if family == "node" else _key(row["tokens"][1])]
            attrs, full = _attributes(family, key, row, component, annotation_index.get((family, key)),
                                      geometry_flags, key in base_nodes if family == "node" else False,
                                      key not in reachable if family == "node" else _key(row["tokens"][2]) not in reachable)
            if family == "node":
                attrs["INV_ELEV"] = _number(row["tokens"][1])
                if row["section"] in {"JUNCTIONS", "STORAGE"} and len(row["tokens"]) > 2:
                    attrs["MAX_DEPTH"] = _number(row["tokens"][2])
                if row["section"] == "JUNCTIONS":
                    attrs["SUR_DEPTH"] = _number(row["tokens"][4]) if len(row["tokens"]) > 4 else 0
            elif row["section"] == "CONDUITS":
                values = interpret_fields("CONDUITS", row["record"])
                for dest, source in (("LENGTH", "length"), ("ROUGHNESS", "roughness"), ("IN_OFFSET", "inlet_offset"), ("OUT_OFFSET", "outlet_offset")):
                    attrs[dest] = _number(values[source])
            if family == "link" and key in cross_sections:
                section = cross_sections[key]
                attrs.update(XS_SHAPE=section["shape"], GEOM1=_number(section["geom1"]), GEOM2=_number(section["geom2"]))
            # Reject DBF numeric overflow before a writer could silently replace a
            # hydraulic value with asterisks. Geometry remains binary double XY.
            for name, kind, width, decimals in _FIELDS:
                value = attrs.get(name)
                if kind == "N" and value is not None and len(f"{value:.{decimals}f}") > width:
                    raise ValueError(f"DBF numeric field overflow: {name}")
                if kind == "C" and value is not None and len(value.encode("utf-8")) > width:
                    raise ValueError(f"DBF text field overflow: {name}")
            features[family + "s"].append((attrs, full, points))
    fields = _flag_fields({flag["code"] for group in features.values() for _, full, _ in group for flag in full["flags"]})
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(dir=target.parent, prefix=".shmm_gis_"))
    try:
        for name, rows in features.items():
            shape_type = shapefile.POINT if name == "nodes" else shapefile.POLYLINE
            with shapefile.Writer(str(stage / name), shapeType=shape_type, encoding="utf-8") as writer:
                for field_name, kind, width, decimals in _FIELDS:
                    writer.field(field_name, kind, width, decimals)
                for field_name in fields.values():
                    writer.field(field_name, "N", 1, 0)
                for attrs, full, points in rows:
                    if points is None:
                        writer.null()
                    elif name == "nodes":
                        writer.point(*points[0])
                    else:
                        writer.line([points])
                    codes = {flag["code"] for flag in full["flags"]}
                    writer.record(*[attrs.get(field_name, "" if kind == "C" else None)
                                    for field_name, kind, *_ in _FIELDS],
                                  *[int(code in codes) for code in fields])
            (stage / f"{name}.prj").write_text(projection.to_wkt(version="WKT1_ESRI"), encoding="utf-8")
            (stage / f"{name}.cpg").write_text("UTF-8", encoding="ascii")
            with shapefile.Reader(str(stage / name), encoding="utf-8") as reader:
                _verify(len(reader) == len(rows), f"{name} record count")
                shape_records = list(reader.iterShapeRecords())
                _verify(len(shape_records) == len(rows), f"{name} shape/record pairing")
                for actual, (attrs, full, points) in zip(shape_records, rows):
                    record = actual.record.as_dict()
                    _verify(set(record) == {item[0] for item in _FIELDS} | set(fields.values()), "field schema")
                    _verify(record["MODEL_ID"] == attrs["MODEL_ID"] and record["QA_KEY"] == attrs["QA_KEY"], "identity")
                    _verify(record["COMP_ID"] == attrs["COMP_ID"] and record["ISLAND_ID"] == attrs["ISLAND_ID"], "component")
                    for field_name, kind, *_ in _FIELDS:
                        expected = attrs.get(field_name, "" if kind == "C" else None)
                        obtained = record[field_name]
                        if isinstance(expected, float):
                            _verify(math.isclose(obtained, expected, rel_tol=0, abs_tol=5.1e-10), field_name)
                        else:
                            _verify(obtained == expected, field_name)
                    codes = {flag["code"] for flag in full["flags"]}
                    _verify(all(record[field_name] == int(code in codes) for code, field_name in fields.items()), "flags")
                    _verify(list(actual.shape.points) == list(points or []), "geometry points")
                    _verify(actual.shape.shapeType == (shape_type if points else shapefile.NULL), "geometry type")
            _verify(CRS.from_wkt((stage / f"{name}.prj").read_text(encoding="utf-8")).equals(projection, ignore_axis_order=True), "CRS")
        full_features = [full for group in features.values() for _, full, _ in group]
        if len({row["qa_key"] for row in full_features}) != len(full_features):
            raise ValueError("Feature QA key collision")
        (stage / "qa_features.json").write_text(json.dumps(full_features, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        (stage / "components.json").write_text(json.dumps(components, indent=2) + "\n", encoding="utf-8")
        columns = ("component_id", "island_id", "is_island", "classification", "node_count", "link_count", "baseline_node_count", "terminal_count", "nodes_without_outlet")
        for filename, selected in (("components.csv", components), ("islands.csv", [row for row in components if row["is_island"] == 1])):
            with (stage / filename).open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=columns)
                writer.writeheader()
                writer.writerows({**{key: row[key] for key in columns if key in row}, "node_count": len(row["node_ids"]), "link_count": len(row["link_ids"])} for row in selected)
        manifest = {"schema_version": 1, "model_sha256": model_hash,
                    "baseline_sha256": sha256(baseline.data).hexdigest() if baseline else None,
                    "crs_wkt": projection.to_wkt(), "reprojected": False,
                    "counts": {"nodes": len(nodes), "links": len(links), "components": len(components),
                               "islands": sum(row["is_island"] == 1 for row in components),
                               "null_geometries": sum(points is None for group in features.values() for _, _, points in group)},
                    "fields": [row[0] for row in _FIELDS], "flag_fields": fields,
                    "model_options": [list(row.tokens) for row in document.records("OPTIONS")],
                    "verification": "shape geometry, records, flags, CRS and source hash verified",
                    "files": {file.name: sha256(file.read_bytes()).hexdigest() for file in sorted(stage.iterdir())}}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if sha256(document.data).hexdigest() != model_hash:
            raise ValueError("Source model changed during export")
        _publish_directory(stage, target)
        return {**manifest, "output_directory": str(target)}
    finally:
        # A failed export leaves no partial public bundle. The only removable
        # directory is the exact temporary child created above, never the target.
        if stage.exists() and stage.resolve().parent == target.parent:
            shutil.rmtree(stage)
