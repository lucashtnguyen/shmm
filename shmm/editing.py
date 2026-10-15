"""Apply explicit finished-record edits while preserving untouched INP text.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-15
Last modified by: Lucas HT Nguyen
Notes: Manually maintained. hymo reads; SHMM modifies and writes. Values use
baseline SWMM field units; no hydraulic parameter or datum inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence

from hymo.document import SWMMDocument, SWMMRecord, read_document
from hymo.schemas import DEFAULTS, FIELDS, REQUIRED, interpret_fields

from .geometry import VertexChange, prepare_vertices, verify_vertices

LOGGER = logging.getLogger(__name__)

# hymo supplies immutable reading schemas. SHMM uses field order/defaults only
# for explicit serialization; schemas never modify or publish model files.
NODE_SECTIONS = ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS")
LINK_SECTIONS = ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS")
# Canonical inventory from EPA SWMM v5.2.4 keywords.c. Unknown spellings,
# abbreviated headers and vendor cards remain lossless but block hydraulic
# edits until their object/dependency meaning has a verified reader contract.
EPA_SECTIONS = frozenset("""TITLE OPTIONS FILES RAINGAGES TEMPERATURE EVAPORATION
SUBCATCHMENTS SUBAREAS INFILTRATION AQUIFERS GROUNDWATER SNOWPACKS JUNCTIONS
OUTFALLS STORAGE DIVIDERS CONDUITS PUMPS ORIFICES WEIRS OUTLETS XSECTIONS
TRANSECTS LOSSES CONTROLS POLLUTANTS LANDUSES BUILDUP WASHOFF COVERAGES
INFLOWS DWF PATTERNS RDII HYDROGRAPHS LOADINGS TREATMENT CURVES TIMESERIES
REPORT COORDINATES VERTICES POLYGONS LABELS SYMBOLS BACKDROP TAGS PROFILES
MAP LID_CONTROLS LID_USAGE GWF ADJUSTMENTS EVENTS STREETS INLET_USAGE INLETS""".split())
NUMBER_PATTERN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
INTEGER_PATTERN = re.compile(r"\+?[0-9]+(?:\.0+)?\Z")


@dataclass(frozen=True)
class Change:
    """One explicit addition or partial update.

    Parameters
    ----------
    action : str
        ``add`` requires a new ID; ``update`` requires an existing ID.
    section : str
        JUNCTIONS, CONDUITS, XSECTIONS, or COORDINATES.
    object_id : str
        Target text ID including leading zeros.
    values : Mapping[str, Any]
        Finished values in baseline units. Omitted update fields remain.
    source_key : str
        Stable caller-owned instruction key recorded in the audit.
    expected : Mapping[str, Any]
        Optional old-value preconditions; mismatches reject the batch.

    Notes
    -----
    Deletion, renaming, rewiring, shape conversion, unit/datum conversion and
    null-as-clear are deferred. Project priorities are not edit instructions.
    """

    action: str
    section: str
    object_id: str
    values: Mapping[str, Any]
    source_key: str
    expected: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeResult:
    """Candidate bytes and audit; neither preview nor apply publishes files."""

    data: bytes
    audit: Mapping[str, Any]


def _key(identifier: str) -> str:
    """Fold ASCII IDs as EPA's case-insensitive hash table does."""
    return identifier.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


def _token(value: Any) -> str:
    """Serialize one safe, unquoted SWMM token."""
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("Fields must be strings or finite numbers, never null/boolean")
    result = str(value)
    if not result or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in result) or any(char in result for char in ';"[]'):
        raise ValueError("Fields must be single unquoted SWMM tokens")
    return result


def _identifier(value: Any) -> str:
    """Require a text identifier so leading zeros cannot be lost implicitly."""
    if not isinstance(value, str) or not value.isascii() or len(value) > 31:
        raise ValueError("SWMM IDs must be ASCII strings of at most 31 characters")
    return _token(value)


def _number(value: str, context: str) -> float:
    """Reject invalid/nonfinite quantities with contextual diagnostics."""
    if not isinstance(value, str) or NUMBER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{context}: expected a finite SWMM number")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{context}: expected a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{context}: expected a finite number")
    return result


def _equal(left: str, right: str, name: str) -> bool:
    """Compare numeric spelling exactly by value and IDs with EPA ASCII folding."""
    if name in {"inlet_node", "outlet_node", "shape"}:
        return _key(left) == _key(right)
    try:
        return _number(left, name) == _number(right, name)
    except ValueError:
        return left == right


def _records(document: SWMMDocument, section: str) -> dict[str, SWMMRecord]:
    """Index uniquely keyed records and reject duplicate identifiers."""
    result: dict[str, SWMMRecord] = {}
    for record in document.records(section):
        identity = _key(record.tokens[0])
        if identity in result:
            raise ValueError(f"[{section}] duplicate ID {record.tokens[0]!r}")
        result[identity] = record
    return result


def _namespace(document: SWMMDocument, sections: Sequence[str]) -> set[str]:
    """Check uniqueness across a SWMM object namespace."""
    result: set[str] = set()
    for section in sections:
        for identity in _records(document, section):
            if identity in result:
                raise ValueError(f"Duplicate object ID across {', '.join(sections)}: {identity}")
            result.add(identity)
    return result


def _options(document: SWMMDocument) -> dict[str, str]:
    """Read settings without changing units, offset conventions, or dates."""
    result: dict[str, str] = {}
    for record in document.records("OPTIONS"):
        if len(record.tokens) != 2:
            raise ValueError("[OPTIONS] requires a key and value per record")
        name = _key(record.tokens[0])
        if name in result:
            raise ValueError(f"[OPTIONS] duplicate setting {name}")
        result[name] = _key(record.tokens[1])
    return result


def _field_values(section: str, record: SWMMRecord) -> dict[str, str]:
    """Interpret supported fields while leaving unrecognized tails intact."""
    return interpret_fields(section, record)


def _validate_fields(section: str, identifier: str, values: Mapping[str, str], options: Mapping[str, str]) -> None:
    """Validate touched engineering fields in baseline units."""
    label = f"[{section}] {identifier}"
    numbers = {}
    for name, value in values.items():
        if name in {"inlet_node", "outlet_node", "shape"}:
            continue
        # ELEVATION offsets are absolute and can be negative. '*' requests
        # the node elevation; DEPTH offsets are nonnegative relative heights.
        if name in {"inlet_offset", "outlet_offset"} and value == "*":
            if options.get("LINK_OFFSETS", "DEPTH") != "ELEVATION":
                raise ValueError(f"{label}: '*' requires LINK_OFFSETS ELEVATION")
            continue
        numbers[name] = _number(value, f"{label}.{name}")
    if section == "CONDUITS":
        for name in ("length", "roughness"):
            if numbers[name] <= 0:
                raise ValueError(f"{label}.{name} must be positive")
        if options.get("LINK_OFFSETS", "DEPTH") == "DEPTH":
            for name in ("inlet_offset", "outlet_offset"):
                if numbers[name] < 0:
                    raise ValueError(f"{label}.{name}: DEPTH offset must be nonnegative")
        if numbers["max_flow"] < 0:
            raise ValueError(f"{label}.max_flow must be nonnegative")
        if _key(values["inlet_node"]) == _key(values["outlet_node"]):
            raise ValueError(f"{label}: endpoints must differ")
    elif section == "JUNCTIONS":
        for name in ("max_depth", "initial_depth", "surcharge_depth", "ponded_area"):
            if numbers[name] < 0:
                raise ValueError(f"{label}.{name} must be nonnegative")
    elif section == "XSECTIONS":
        shape = _key(values["shape"])
        if shape not in {"CIRCULAR", "FORCE_MAIN"}:
            raise NotImplementedError(f"STUB_XSECTION_SHAPES: editing {shape} is deferred")
        if numbers["geom1"] <= 0:
            raise ValueError(f"{label}.geom1 (diameter) must be positive")
        # FORCE_MAIN Geom2 is H-W C or Darcy-Weisbach roughness according to
        # FORCE_MAIN_EQUATION. It must never be treated as Manning n.
        if shape == "FORCE_MAIN" and numbers["geom2"] <= 0:
            raise ValueError(f"{label}.geom2 (force-main roughness) must be positive")
        for name in ("barrels", "culvert"):
            minimum = 1 if name == "barrels" else 0
            # EPA uses atoi then char storage for barrels. Exponent spellings
            # therefore must not be accepted as though atoi parsed float text.
            maximum = 127 if name == "barrels" else 57
            if INTEGER_PATTERN.fullmatch(values[name]) is None or numbers[name] != int(numbers[name]) or not minimum <= numbers[name] <= maximum:
                raise ValueError(f"{label}.{name}: invalid integer")


def _validate_candidate(document: SWMMDocument, touched: set[tuple[str, str]]) -> None:
    """Validate supported network relations, without claiming engine acceptance."""
    options = _options(document)
    if options.get("FLOW_UNITS") not in {"CFS", "GPM", "MGD", "CMS", "LPS", "MLD"}:
        raise ValueError("[OPTIONS] explicit supported FLOW_UNITS is required")
    if options.get("LINK_OFFSETS", "DEPTH") not in {"DEPTH", "ELEVATION"}:
        raise ValueError("[OPTIONS] LINK_OFFSETS must be DEPTH or ELEVATION")
    nodes = _namespace(document, NODE_SECTIONS)
    links = _namespace(document, LINK_SECTIONS)
    cross_sections = _records(document, "XSECTIONS")
    for section in LINK_SECTIONS:
        for record in document.records(section):
            if len(record.tokens) < 3:
                raise ValueError(f"[{section}] incomplete link record")
            for endpoint in record.tokens[1:3]:
                if _key(endpoint) not in nodes:
                    raise ValueError(f"[{section}] {record.tokens[0]}: missing endpoint {endpoint}")
            if section in {"CONDUITS", "ORIFICES", "WEIRS"} and _key(record.tokens[0]) not in cross_sections:
                raise ValueError(f"[{section}] {record.tokens[0]}: missing cross section")
    for identity in cross_sections:
        if identity not in links:
            raise ValueError(f"[XSECTIONS] {identity}: missing link")
    for section in ("DWF", "INFLOWS", "RDII", "COORDINATES"):
        for record in document.records(section):
            if _key(record.tokens[0]) not in nodes:
                raise ValueError(f"[{section}] {record.tokens[0]}: missing node")
    for section in ("LOSSES", "VERTICES"):
        for record in document.records(section):
            if _key(record.tokens[0]) not in links:
                raise ValueError(f"[{section}] {record.tokens[0]}: missing link")
    for section, identity in touched:
        record = _records(document, section)[identity]
        if section == "XSECTIONS" and identity not in _records(document, "CONDUITS"):
            raise NotImplementedError("STUB_XSECTION_LINK_TYPES: only conduit cross-section edits are supported")
        _validate_fields(section, record.tokens[0], _field_values(section, record), options)
        if section in {"CONDUITS", "XSECTIONS"}:
            cross_section = cross_sections[identity]
            values = _field_values("XSECTIONS", cross_section)
            if _key(values["shape"]) == "FORCE_MAIN":
                # EPA 5.2.4 project.c defaults to Dynamic Wave and H-W. Only
                # Dynamic Wave uses the supplied pressure friction equation;
                # do not accept a touched pressure pipe as an ordinary conduit.
                # This is a supported editing contract, not full engine QA.
                if options.get("FLOW_ROUTING", "DYNWAVE") != "DYNWAVE":
                    raise ValueError("FORCE_MAIN editing requires FLOW_ROUTING DYNWAVE")
                if options.get("FORCE_MAIN_EQUATION", "H-W") not in {"H-W", "D-W"}:
                    raise ValueError("FORCE_MAIN_EQUATION must be H-W or D-W")
                _validate_fields("XSECTIONS", cross_section.tokens[0], values, options)


def _patch_line(line: str, record: SWMMRecord, section: str, values: Mapping[str, str]) -> str:
    """Replace changed spans only; preserve whitespace, comments, and extra tails."""
    fields = FIELDS[section]
    highest = max(fields.index(name) + 1 for name in values)
    result = line
    delta = 0
    for name, value in sorted(values.items(), key=lambda item: fields.index(item[0]), reverse=True):
        position = fields.index(name) + 1
        if position < len(record.tokens) and not _equal(record.tokens[position], value, name):
            start, stop = record.spans[position]
            result = result[:start] + value + result[stop:]
            delta += len(value) - (stop - start)
    if highest >= len(record.tokens):
        # Append only documented missing optional fields, before comments.
        tail = []
        for position in range(len(record.tokens), highest + 1):
            name = fields[position - 1]
            tail.append(values[name] if name in values else DEFAULTS[section][name])
        insertion = record.spans[-1][1] + delta
        result = result[:insertion] + " " + " ".join(tail) + result[insertion:]
    return result


def preview_changes(document: SWMMDocument, changes: Sequence[Change], *, expected_hash: str | None = None,
                    vertex_changes: Sequence[VertexChange] = ()) -> ChangeResult:
    """Validate a batch and return its exact candidate bytes and audit in memory.

    Parameters
    ----------
    document : hymo.document.SWMMDocument
        Read-only baseline with source text and token locations.
    changes : Sequence[Change]
        Explicit additions or partial updates; no inferred deletions.
    expected_hash : str, optional
        SHA-256 baseline precondition.
    vertex_changes : Sequence[VertexChange], optional
        Add-only ordered interior XY for existing or same-batch links. Their
        candidate endpoint nodes must have finite COORDINATES. Map geometry
        never supplies hydraulic lengths or elevations.

    Returns
    -------
    ChangeResult
        Candidate bytes and before/after fields tied to source instructions.

    Raises
    ------
    ValueError
        Invalid instructions, stale inputs, bounds, or supported references.
    NotImplementedError
        An edit targets deferred functionality.

    Notes
    -----
    No files are written. Every batch succeeds as a whole or raises. No-op
    previews preserve bytes even for sections without interpreted schemas.
    """
    digest = sha256(document.data).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError("Stale baseline: SHA-256 does not match expected_hash")
    lines = list(document.lines)
    indexes = {section: _records(document, section) for section in FIELDS}
    options = _options(document)
    opaque = sorted(section for section in set(document.sections) - EPA_SECTIONS if document.records(section))
    if opaque and any(change.section.upper().strip("[]") != "COORDINATES" for change in changes):
        raise NotImplementedError(f"STUB_OPAQUE_DEPENDENCIES: hydraulic edits blocked by {opaque}")
    touched: set[tuple[str, str]] = set()
    additions: dict[str, list[str]] = {}
    audit_rows = []
    for change in changes:
        section = change.section.upper().strip("[]")
        if section not in FIELDS:
            raise NotImplementedError(f"STUB_SECTION_EDITING: [{section}] edits are deferred")
        if change.action not in {"add", "update"}:
            raise NotImplementedError("STUB_DELETE_RENAME: only add/update are supported")
        identity = _key(_identifier(change.object_id))
        if not isinstance(change.source_key, str) or not change.source_key.strip():
            raise ValueError("An explicit source_key is required")
        target = (section, identity)
        if target in touched:
            raise ValueError(f"Conflicting instructions for [{section}] {change.object_id}")
        touched.add(target)
        if not change.values:
            raise ValueError("Each instruction must supply at least one field")
        unknown = (set(change.values) | set(change.expected)) - set(FIELDS[section])
        if unknown:
            raise ValueError(f"[{section}]: unknown fields {sorted(unknown)}")
        supplied = {name: _token(value) for name, value in change.values.items()}
        record = indexes[section].get(identity)
        before: dict[str, str] | None = None
        if change.action == "update":
            if record is None:
                raise ValueError(f"[{section}] {change.object_id}: update target is missing")
            before = _field_values(section, record)
            for name, expected in change.expected.items():
                if not _equal(before[name], _token(expected), name):
                    raise ValueError(f"[{section}] {change.object_id}.{name}: stale old value")
            for name in {"inlet_node", "outlet_node", "shape"} & set(supplied):
                if not _equal(before[name], supplied[name], name):
                    raise NotImplementedError("STUB_REWIRE_CONVERSION: endpoint/shape changes are deferred")
            after = {**before, **supplied}
            _validate_fields(section, change.object_id, after, options)
            lines[record.line_index] = _patch_line(lines[record.line_index], record, section, supplied)
        else:
            if record is not None:
                raise ValueError(f"[{section}] {change.object_id}: addition already exists")
            if change.expected:
                raise ValueError("Additions cannot have old-value preconditions")
            missing = set(FIELDS[section][:REQUIRED[section]]) - set(supplied)
            if missing:
                raise ValueError(f"[{section}] {change.object_id}: missing required fields {sorted(missing)}")
            after = {**DEFAULTS[section], **supplied}
            _validate_fields(section, change.object_id, after, options)
            highest = max(FIELDS[section].index(name) for name in supplied)
            tokens = [change.object_id] + [after[name] for name in FIELDS[section][:highest + 1]]
            additions.setdefault(section, []).append(" ".join(tokens) + document.newline)
        audit_rows.append({"action": change.action, "section": section, "object_id": change.object_id,
                           "source_key": change.source_key, "before": before, "after": after,
                           "fields": sorted(supplied), "changed": before is None or any(not _equal(before[name], value, name) for name, value in supplied.items())})
    vertex_rows, vertex_audit = prepare_vertices(document, vertex_changes)
    if vertex_rows:
        additions["VERTICES"] = vertex_rows
    # Insert existing sections right-to-left at original boundaries, then append
    # absent sections separately so inserts never change another source index.
    existing = [(section, rows) for section, rows in additions.items() if section in document.sections]
    for section, rows in sorted(existing, key=lambda item: document.sections[item[0]].end_line, reverse=True):
        position = document.sections[section].end_line
        if position and not lines[position - 1].endswith(("\n", "\r")):
            lines[position - 1] += document.newline
        lines[position:position] = rows
    for section, rows in additions.items():
        if section not in document.sections:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += document.newline
            lines.extend([document.newline, f"[{section}]" + document.newline, *rows])
    candidate_text = "".join(lines)
    # Encoding aliases such as utf-8-sig can introduce a BOM on re-encoding a
    # BOM-less source. Preserve original bytes for every byte-neutral plan.
    candidate_data = document.data if candidate_text == document.text else candidate_text.encode(document.encoding)
    candidate = SWMMDocument.from_bytes(candidate_data, encoding=document.encoding)
    if changes:
        _validate_candidate(candidate, touched)
    for row in audit_rows:
        observed = _field_values(row["section"], _records(candidate, row["section"])[_key(row["object_id"])])
        if any(not _equal(observed[name], value, name) for name, value in row["after"].items()):
            raise ValueError("Candidate readback disagrees with the edit audit")
    if vertex_changes:
        links = {identity: record for section in LINK_SECTIONS
                 for identity, record in _records(candidate, section).items()}
        _namespace(candidate, LINK_SECTIONS)
        verify_vertices(candidate, vertex_audit, links)
    audit_rows.extend(vertex_audit)
    interpreted_sections = set(FIELDS) | {"OPTIONS", "TITLE"}
    if vertex_changes:
        interpreted_sections.add("VERTICES")
    audit = {"schema_version": "1", "baseline_sha256": digest,
             "candidate_sha256": sha256(candidate.data).hexdigest(), "options": options,
             "changes": audit_rows, "validation": "supported structural checks passed" if changes or vertex_changes else "no-op byte preservation",
             "engine_check": "not run", "uninterpreted_sections": sorted(set(document.sections) - interpreted_sections),
             "validation_limits": ["No complete deferred-card grammar/dependency validation", "No datum or calibrated hydraulic acceptance", "Effective initial-depth/crown checks require engine validation"]}
    LOGGER.info("Validated %d instructions; candidate SHA-256 %s", len(changes) + len(vertex_changes), audit["candidate_sha256"])
    return ChangeResult(candidate.data, audit)


def apply_changes(document: SWMMDocument, changes: Sequence[Change], *, expected_hash: str | None = None,
                  vertex_changes: Sequence[VertexChange] = ()) -> ChangeResult:
    """Apply in memory; parameters/returns match ``preview_changes`` exactly."""
    return preview_changes(document, changes, expected_hash=expected_hash, vertex_changes=vertex_changes)


def _stage_file(path: Path, data: bytes) -> Path:
    """Write and flush a same-directory staging file without publishing it."""
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    stage = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        stage.unlink(missing_ok=True)
        raise
    return stage


def _publish_file(stage: Path, target: Path) -> None:
    """Atomically publish without overwrite using native filesystem semantics."""
    if os.name == "nt":
        # Windows rename fails if target exists; unlike hard links, it does not
        # require a link operation allowed by the execution sandbox.
        os.rename(stage, target)
    else:
        os.link(stage, target)


def edit_model(source_path: str | Path, changes: Sequence[Change], output_path: str | Path,
               audit_path: str | Path, *, encoding: str = "utf-8", expected_hash: str | None = None,
               vertex_changes: Sequence[VertexChange] = ()) -> ChangeResult:
    """Publish a separate readback-checked model followed by a completion audit.

    Parameters
    ----------
    source_path, output_path, audit_path : str or Path
        Distinct paths. Output/audit must not exist; parents must exist.
    changes : Sequence[Change]
        Finished explicit instructions.
    encoding : str
        Explicit input encoding; no fallback.
    expected_hash : str, optional
        Baseline SHA-256 precondition.
    vertex_changes : Sequence[VertexChange], optional
        Add-only finished interior map vertices in the same transaction.

    Returns
    -------
    ChangeResult
        Published bytes and audit.

    Notes
    -----
    Audit publication marks completion. Consumers must require both files and
    verify the candidate hash: a process interruption can leave a candidate
    without its audit. Windows uses non-overwriting rename; POSIX uses links.
    """
    source, output, audit = (Path(path).resolve() for path in (source_path, output_path, audit_path))
    if len({source, output, audit}) != 3:
        raise ValueError("Source, candidate, and audit paths must differ")
    for path in (output, audit):
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise FileNotFoundError(path.parent)
    document = read_document(source, encoding=encoding)
    result = apply_changes(document, changes, expected_hash=expected_hash, vertex_changes=vertex_changes)
    stage = _stage_file(output, result.data)
    audit_stage: Path | None = None
    published_output = False
    try:
        if read_document(stage, encoding=encoding).data != result.data:
            raise ValueError("Staged model readback mismatch")
        audit_stage = _stage_file(audit, (json.dumps(result.audit, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        if source.read_bytes() != document.data:
            raise ValueError("Source changed during publication")
        # Atomic create-if-absent; never replace a concurrent user's file.
        _publish_file(stage, output)
        published_output = True
        _publish_file(audit_stage, audit)
    except BaseException:
        if published_output:
            output.unlink(missing_ok=True)
        raise
    finally:
        stage.unlink(missing_ok=True)
        if audit_stage is not None:
            audit_stage.unlink(missing_ok=True)
    LOGGER.info("Published candidate %s and completion audit %s", output, audit)
    return result
