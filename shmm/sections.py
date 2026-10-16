"""Publish explicitly finished section replacements with exact model QA.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-16
Notes: Manually maintained. Upstream owns engineering assumptions, aggregation,
units and scenario selection. This API never derives replacement records.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from hymo.document import SWMMDocument, read_document
from hymo.schemas import interpret_fields

from .comparison import ModelDiff, _effects, _text_diff, write_diff_reports
from .editing import (LINK_SECTIONS, NODE_SECTIONS, _identifier, _key,
                      _namespace, _number, _options, _publish_file, _records,
                      _stage_file, _validate_candidate, _validate_fields)


@dataclass(frozen=True)
class SectionPatch:
    """An explicit complete replacement or deletion of one section.

    Parameters
    ----------
    section : str
        Full section name without brackets; case insensitive.
    lines : sequence of str
        Complete section body as individual lines without newline characters.
        Comments and quoted SWMM values are accepted literally. An empty body
        clears all records. Unmentioned sections retain their original bytes.
    source_key, basis : str
        Nonempty instruction identity and engineering/source justification.
    object_evidence : mapping, optional
        JSON-compatible evidence keyed by model object ID (ASCII case
        insensitive). Field assignments, source observations, assumption flags
        and aggregation membership belong here. Section basis remains mandatory.
    delete : bool, optional
        Remove the entire section, including its header. Requires empty lines
        and an existing section. Nothing is deleted by omission of a patch.

    Notes
    -----
    Replacement includes every body line, including existing comments. This
    coarse operation is for finished networks, rewiring, explicit removals and
    forcing changes; use Change for narrow preserving record edits instead.
    """

    section: str
    lines: Sequence[str]
    source_key: str
    basis: str
    object_evidence: Mapping[str, Any] = field(default_factory=dict)
    delete: bool = False


@dataclass(frozen=True)
class SectionPatchResult:
    """Exact bytes, completion audit, preview and optional written comparison."""

    data: bytes
    audit: Mapping[str, Any]
    diff: ModelDiff
    written_diff: ModelDiff | None = None


def _json_copy(value: Any) -> Any:
    """Snapshot finite JSON metadata so later caller mutation cannot alter QA."""
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _section_text(document: SWMMDocument, name: str) -> str:
    """Return the exact decoded header and body of an existing section."""
    section = document.sections.get(name)
    return "" if section is None else "".join(document.lines[section.header_line:section.end_line])


def _prepare(document: SWMMDocument, patches: Sequence[SectionPatch], baseline_sha256: str) -> tuple[SWMMDocument, list[dict[str, Any]]]:
    """Apply literal bodies while retaining all unaddressed source slices."""
    actual_hash = sha256(document.data).hexdigest()
    if baseline_sha256 != actual_hash:
        raise ValueError("Baseline SHA-256 precondition failed")
    bodies: dict[str, str] = {}
    requests: list[dict[str, Any]] = []
    source_keys: set[str] = set()
    for patch in patches:
        if not isinstance(patch.section, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", patch.section) is None:
            raise ValueError("section must be a complete name without brackets")
        name = patch.section.upper()
        if name in bodies:
            raise ValueError(f"Duplicate section patch [{name}]")
        for label, value in (("source_key", patch.source_key), ("basis", patch.basis)):
            if not isinstance(value, str) or not value.strip() or not value.isprintable():
                raise ValueError(f"{label} must be nonempty printable single-line text")
        if patch.source_key in source_keys:
            raise ValueError("Section patch source_key values must be unique")
        source_keys.add(patch.source_key)
        if not isinstance(patch.delete, bool):
            raise ValueError("delete must be boolean")
        if isinstance(patch.lines, (str, bytes)):
            raise ValueError("lines must be a sequence of individual body lines")
        lines = tuple(patch.lines)
        for line in lines:
            if not isinstance(line, str) or any(ord(c) < 32 and c != "\t" or ord(c) == 127 for c in line):
                raise ValueError("Body lines must be text without newline/control characters")
            if line.lstrip().startswith("["):
                raise ValueError("Section header injection in replacement body")
        if patch.delete and (lines or name not in document.sections):
            raise ValueError("Deletion requires empty lines and an existing section")
        evidence: dict[str, Any] = {}
        if not isinstance(patch.object_evidence, Mapping):
            raise ValueError("object_evidence must be a mapping")
        for identity, item in patch.object_evidence.items():
            folded = _key(_identifier(identity))
            if folded in evidence:
                raise ValueError("Duplicate case-insensitive object evidence ID")
            evidence[folded] = _json_copy(item)
        previous = _section_text(document, name)
        if patch.delete:
            replacement = ""
        else:
            existing = document.sections.get(name)
            header = document.lines[existing.header_line] if existing else f"[{name}]{document.newline}"
            if not header.endswith(("\n", "\r")):
                header += document.newline
            replacement = header + "".join(line + document.newline for line in lines)
        bodies[name] = replacement
        requests.append({"section": name, "object_id": "*", "action": "delete_section" if patch.delete else "replace_section",
                         "source_key": patch.source_key, "basis": patch.basis, "fields": ["section_body"],
                         "field_units": {"section_body": "finished SWMM model units"},
                         "before": previous, "after": replacement, "changed": previous != replacement,
                         "evidence": {"basis": patch.basis, "object_evidence": evidence},
                         "before_sha256": sha256(previous.encode(document.encoding)).hexdigest(),
                         "after_sha256": sha256(replacement.encode(document.encoding)).hexdigest()})
    output: list[str] = []
    cursor = 0
    for name, section in document.sections.items():
        output.extend(document.lines[cursor:section.header_line])
        output.append(bodies.pop(name) if name in bodies else _section_text(document, name))
        cursor = section.end_line
    output.extend(document.lines[cursor:])
    for replacement in bodies.values():
        preceding = next((text for text in reversed(output) if text), "")
        if preceding and not preceding.endswith(("\n", "\r")):
            # A missing newline at EOF is only changed when appending a section.
            # Refuse rather than silently mutate an untouched source section.
            raise ValueError("Appending a section requires a baseline final newline")
        output.append(replacement)
    candidate = SWMMDocument.from_bytes("".join(output).encode(document.encoding), encoding=document.encoding)
    return candidate, requests


def _require_reference(identity: str, namespace: set[str], context: str) -> None:
    """Reject dangling references using EPA ASCII case folding."""
    if _key(identity) not in namespace:
        raise ValueError(f"{context}: missing reference {identity!r}")


def _validate_dependencies(document: SWMMDocument, patched_sections: set[str], *, require_connected: bool, require_terminal_routes: bool) -> dict[str, Any]:
    """Check supported dependencies and final directed/undirected graph.

    Notes
    -----
    Graph direction follows declared link endpoints, including pumps. Reverse
    hydraulic flow and pump operation are not inferred. Terminal routes end at
    declared OUTFALLS; an outfall itself has a zero-link route. This is input
    integrity, not simulation or acceptance of provisional engineering values.
    """
    _validate_candidate(document, set())
    nodes = _namespace(document, NODE_SECTIONS)
    links = _namespace(document, LINK_SECTIONS)
    conduit_ids = set(_records(document, "CONDUITS"))
    cross_section_ids = conduit_ids | set(_records(document, "ORIFICES")) | set(_records(document, "WEIRS"))
    _records(document, "COORDINATES")
    for row in document.records("XSECTIONS"):
        _require_reference(row.tokens[0], cross_section_ids, "[XSECTIONS] supported link type")
    for row in document.records("LOSSES"):
        _require_reference(row.tokens[0], conduit_ids, "[LOSSES] conduit")
    for section in (*NODE_SECTIONS, *LINK_SECTIONS, "COORDINATES", "XSECTIONS"):
        for record in document.records(section):
            _identifier(record.tokens[0])
    # Named field checks apply only to replaced supported records. Shape-specific
    # grammars outside the existing contract stay explicit solver-review limits.
    options = _options(document)
    for section in patched_sections & {"JUNCTIONS", "CONDUITS", "COORDINATES", "XSECTIONS"}:
        for record in document.records(section):
            values = interpret_fields(section, record)
            if section != "XSECTIONS" or _key(values["shape"]) in {"CIRCULAR", "FORCE_MAIN"}:
                _validate_fields(section, record.tokens[0], values, options)
                if section == "XSECTIONS" and _key(values["shape"]) == "FORCE_MAIN":
                    if options.get("FLOW_ROUTING", "DYNWAVE") != "DYNWAVE" or options.get("FORCE_MAIN_EQUATION", "H-W") not in {"H-W", "D-W"}:
                        raise ValueError("FORCE_MAIN requires DYNWAVE and H-W or D-W friction")
    for section in ("COORDINATES", "VERTICES"):
        for row in document.records(section):
            if len(row.tokens) != 3:
                raise ValueError(f"[{section}] requires object ID and two coordinates")
            for value in row.tokens[1:]:
                _number(value, f"[{section}] {row.tokens[0]}")
    curves = {_key(row.tokens[0]) for row in document.records("CURVES")}
    timeseries = {_key(row.tokens[0]) for row in document.records("TIMESERIES")}
    patterns = {_key(row.tokens[0]) for row in document.records("PATTERNS")}
    subcatchments = {_key(row.tokens[0]) for row in document.records("SUBCATCHMENTS")}
    for row in document.records("PUMPS"):
        if len(row.tokens) < 4:
            raise ValueError("[PUMPS] requires endpoints and a pump curve")
        if row.tokens[3] != "*":
            _require_reference(row.tokens[3], curves, "[PUMPS] curve")
    for row in document.records("OUTFALLS"):
        if len(row.tokens) < 3:
            raise ValueError("[OUTFALLS] requires elevation and type")
        kind = _key(row.tokens[2])
        if kind in {"TIMESERIES", "TIDAL"}:
            if len(row.tokens) < 4:
                raise ValueError("[OUTFALLS] missing boundary reference")
            _require_reference(row.tokens[3], timeseries if kind == "TIMESERIES" else curves, "[OUTFALLS] boundary")
    for row in document.records("STORAGE"):
        if len(row.tokens) > 5 and _key(row.tokens[4]) == "TABULAR":
            _require_reference(row.tokens[5], curves, "[STORAGE] curve")
    for row in document.records("RAINGAGES"):
        if len(row.tokens) > 5 and _key(row.tokens[4]) == "TIMESERIES":
            _require_reference(row.tokens[5], timeseries, "[RAINGAGES] timeseries")
    for row in document.records("INFLOWS"):
        if len(row.tokens) < 3:
            raise ValueError("[INFLOWS] requires node, constituent and timeseries")
        if row.tokens[2] != "*":
            _require_reference(row.tokens[2], timeseries, "[INFLOWS] timeseries")
        if len(row.tokens) > 7 and row.tokens[7] != "*":
            _require_reference(row.tokens[7], patterns, "[INFLOWS] pattern")
    for row in document.records("DWF"):
        if len(row.tokens) < 3:
            raise ValueError("[DWF] requires node, constituent and average value")
        for identity in row.tokens[3:]:
            if identity != "*":
                _require_reference(identity, patterns, "[DWF] pattern")
    for section in ("TREATMENT",):
        for row in document.records(section):
            _require_reference(row.tokens[0], nodes, f"[{section}]")
    for row in document.records("SUBCATCHMENTS"):
        if len(row.tokens) < 3:
            raise ValueError("[SUBCATCHMENTS] missing outlet")
        _require_reference(row.tokens[2], nodes | subcatchments, "[SUBCATCHMENTS] outlet")
    for row in document.records("DIVIDERS"):
        if len(row.tokens) < 3:
            raise ValueError("[DIVIDERS] missing diverted link")
        _require_reference(row.tokens[2], links, "[DIVIDERS] link")
    # Control clauses carry explicit object type before ID, including compound
    # AND/OR conditions. SIMULATION, RULE, PRIORITY and expression tokens are
    # deliberately not treated as object IDs.
    node_types = {"NODE", "JUNCTION", "STORAGE", "OUTFALL", "DIVIDER"}
    link_types = {"LINK", "CONDUIT", "PUMP", "ORIFICE", "WEIR", "OUTLET"}
    for row in document.records("CONTROLS"):
        tokens = row.tokens
        for index, token in enumerate(tokens[:-1]):
            kind = _key(token)
            preceding = _key(tokens[index - 1]) if index > 0 else ""
            if preceding in {"IF", "AND", "OR", "THEN", "ELSE", "=", "<>", "<", ">", "<=", ">="} and kind in node_types | link_types:
                _require_reference(tokens[index + 1], nodes if kind in node_types else links, "[CONTROLS]")
            if preceding == "=" and kind in {"CURVE", "TIMESERIES"}:
                _require_reference(tokens[index + 1], curves if kind == "CURVE" else timeseries, "[CONTROLS] modulated setting")
    for row in document.records("TAGS"):
        if len(row.tokens) > 1 and _key(row.tokens[0]) in {"NODE", "LINK", "SUBCATCH"}:
            namespace = nodes if _key(row.tokens[0]) == "NODE" else links if _key(row.tokens[0]) == "LINK" else subcatchments
            _require_reference(row.tokens[1], namespace, "[TAGS]")
    for row in document.records("REPORT"):
        if _key(row.tokens[0]) in {"NODES", "LINKS"}:
            namespace = nodes if _key(row.tokens[0]) == "NODES" else links
            for identity in row.tokens[1:]:
                if _key(identity) not in {"ALL", "NONE"}:
                    _require_reference(identity, namespace, "[REPORT]")
    for row in document.records("PROFILES"):
        for identity in row.tokens[1:]:
            _require_reference(identity, links, "[PROFILES]")
    neighbors = {node: set() for node in nodes}
    predecessors = {node: set() for node in nodes}
    for section in LINK_SECTIONS:
        for row in document.records(section):
            upstream, downstream = map(_key, row.tokens[1:3])
            if upstream == downstream:
                raise ValueError(f"[{section}] {row.tokens[0]}: endpoints must differ")
            neighbors[upstream].add(downstream)
            neighbors[downstream].add(upstream)
            predecessors[downstream].add(upstream)
    components: list[list[str]] = []
    unseen = set(nodes)
    while unseen:
        start = min(unseen)
        reached, queue = {start}, deque([start])
        while queue:
            for neighbor in neighbors[queue.popleft()] - reached:
                reached.add(neighbor)
                queue.append(neighbor)
        unseen -= reached
        components.append(sorted(reached))
    terminals = set(_records(document, "OUTFALLS"))
    reachable, queue = set(terminals), deque(terminals)
    while queue:
        for upstream in predecessors[queue.popleft()] - reachable:
            reachable.add(upstream)
            queue.append(upstream)
    unrouted = sorted(nodes - reachable)
    if require_connected and len(components) != 1:
        raise ValueError(f"Final network must have one connected component; found {len(components)}")
    if require_terminal_routes and unrouted:
        raise ValueError(f"Final nodes lack directed outfall routes: {', '.join(unrouted)}")
    return {"node_count": len(nodes), "link_count": len(links), "component_count": len(components),
            "components": components, "outfalls": sorted(terminals), "nodes_without_terminal_route": unrouted,
            "require_connected": require_connected, "require_terminal_routes": require_terminal_routes}


def _effect_signature(row: Mapping[str, Any]) -> str:
    """Match lexical occurrences without collapsing repeated curve/forcing IDs."""
    return json.dumps({key: row[key] for key in ("section", "object_id", "field", "before", "after")}, sort_keys=True)


def _comparison(baseline: SWMMDocument, actual: SWMMDocument, expected: SWMMDocument, requests: list[dict[str, Any]], stage: str) -> ModelDiff:
    """Reuse field comparison and report rendering with section-owned evidence."""
    effects, coverage = _effects(baseline, actual)
    expected_effects, _ = _effects(baseline, expected)
    remaining = Counter(_effect_signature(row) for row in expected_effects)
    by_section = {request["section"]: request for request in requests}
    for row in effects:
        signature = _effect_signature(row)
        requested = remaining[signature] > 0
        if requested:
            remaining[signature] -= 1
        row["reconciliation"] = "requested_effect" if requested else "unexpected_effect"
        request = by_section.get(row["section"])
        evidence = request["evidence"] if request else {}
        row["source_keys"] = [request["source_key"]] if request else []
        row["evidence"] = [{"basis": request["basis"], "object": evidence["object_evidence"].get(_key(row["object_id"]), {})}] if request else []
    missing = []
    for row in expected_effects:
        signature = _effect_signature(row)
        if remaining[signature]:
            missing.append({**row, "reconciliation": "missing_effect"})
            remaining[signature] -= 1
    matches = actual.data == expected.data
    report = {"schema_version": "1", "operation_contract": "finished_section_patch_v1", "stage": stage,
              "baseline_sha256": sha256(baseline.data).hexdigest(), "candidate_sha256": sha256(actual.data).hexdigest(),
              "expected_candidate_sha256": sha256(expected.data).hexdigest(), "requested_operations": requests,
              "effects": effects, "missing_expected_effects": missing,
              "verification": {"matches_expected": matches, "exact_bytes_checked": True,
                               "unexpected_effects": sum(row["reconciliation"] == "unexpected_effect" for row in effects),
                               "missing_effects": len(missing), "requested_noops": sum(not row["changed"] for row in requests)},
              "section_matching": coverage, "raw_text_diff": _text_diff(baseline, actual, "candidate"),
              "unexpected_text_diff": "" if matches else _text_diff(expected, actual, "written candidate"),
              "limits": ["Whole-section replacements are explicit; upstream supplies every body record and engineering decision.",
                         "Named fields use hymo schemas; other records use ordered lexical comparison.",
                         "Supported references and graph routes are checked; complete EPA grammar and hydraulic acceptance require a solver."]}
    return ModelDiff(actual.data, _json_copy(report))


def preview_section_patches(document: SWMMDocument, patches: Sequence[SectionPatch], *, baseline_sha256: str,
                            require_connected: bool = False, require_terminal_routes: bool = False) -> SectionPatchResult:
    """Prepare a hash-guarded final model and both lexical and field-level QA.

    Parameters
    ----------
    document : SWMMDocument
        Immutable baseline read using hymo and an explicit source encoding.
    patches : sequence of SectionPatch
        Complete finished bodies; unspecified sections are preserved exactly.
    baseline_sha256 : str
        Mandatory exact source SHA-256, including comments and line endings.
    require_connected, require_terminal_routes : bool, optional
        Enforce one weak component and/or a declared directed path from every
        node to an OUTFALL. Both are false by default for general model editing.

    Returns
    -------
    SectionPatchResult
        Candidate bytes, source/object evidence, graph and preservation audit,
        and a ModelDiff compatible with write_diff_reports. No files are written.

    Raises
    ------
    ValueError
        Stale hash, ambiguous/injected input, dangling supported dependencies,
        ID collision, invalid supported values or failed topology acceptance.
    """
    if not isinstance(require_connected, bool) or not isinstance(require_terminal_routes, bool):
        raise ValueError("Topology acceptance flags must be boolean")
    candidate, requests = _prepare(document, patches, baseline_sha256)
    patched_sections = {request["section"] for request in requests}
    topology = _validate_dependencies(candidate, patched_sections, require_connected=require_connected,
                                      require_terminal_routes=require_terminal_routes)
    preservation = []
    for name in document.sections.keys() - patched_sections:
        before, after = _section_text(document, name), _section_text(candidate, name)
        if before != after:
            raise ValueError(f"Unrequested section changed: [{name}]")
        preservation.append({"section": name, "sha256": sha256(before.encode(document.encoding)).hexdigest(), "exact": True})
    diff = _comparison(document, candidate, candidate, requests, "preview")
    audit = {"schema_version": "1", "operation_contract": "finished_section_patch_v1",
             "baseline_sha256": baseline_sha256, "candidate_sha256": sha256(candidate.data).hexdigest(),
             "section_patches": requests, "preserved_sections": sorted(preservation, key=lambda row: row["section"]),
             "topology": topology, "status": "preview", "verification": diff.report["verification"]}
    return SectionPatchResult(candidate.data, _json_copy(audit), diff)


def compare_written_sections(baseline: SWMMDocument, candidate: SWMMDocument, patches: Sequence[SectionPatch], *,
                             baseline_sha256: str, require_connected: bool = False,
                             require_terminal_routes: bool = False) -> ModelDiff:
    """Independently replay section requests and compare an actual readback.

    Parameters
    ----------
    baseline, candidate : SWMMDocument
        Frozen baseline and actual written model re-read with hymo.
    patches : sequence of SectionPatch
        The identical finished requests used for the reviewed preview.
    baseline_sha256 : str
        Exact frozen baseline hash precondition.
    require_connected, require_terminal_routes : bool, optional
        Same acceptance flags used in preview.

    Returns
    -------
    ModelDiff
        Exact-byte reconciliation, field effects and full text differences.
        A malformed candidate must first pass hymo reading; a readable mismatch
        is reported, never silently rewritten or treated as successful.
    """
    expected = preview_section_patches(baseline, patches, baseline_sha256=baseline_sha256,
                                       require_connected=require_connected, require_terminal_routes=require_terminal_routes)
    return _comparison(baseline, candidate, SWMMDocument.from_bytes(expected.data, encoding=baseline.encoding),
                       list(expected.audit["section_patches"]), "written_model")


def publish_section_patches(source_path: str | Path, output_path: str | Path, patches: Sequence[SectionPatch], *,
                             baseline_sha256: str, audit_path: str | Path, report_directory: str | Path | None = None,
                             preview_prefix: str = "preview_diff", written_prefix: str = "written_model_diff",
                             encoding: str = "utf-8", require_connected: bool = False,
                             require_terminal_routes: bool = False) -> SectionPatchResult:
    """Publish a new model with preview, independent readback and completion audit.

    Parameters
    ----------
    source_path, output_path : str or Path
        Distinct baseline and new candidate files. Source is never modified.
    patches : sequence of SectionPatch
        Complete finished section requests. Engineering preparation is upstream.
    baseline_sha256 : str
        Mandatory exact source hash precondition, rechecked during publication.
    audit_path : str or Path
        New completion audit file, published last after successful readback.
    report_directory : str or Path, optional
        Existing directory for JSON/CSV/HTML diffs; defaults to candidate parent.
    preview_prefix, written_prefix : str, optional
        Distinct simple stems for the two report sets.
    encoding : str, optional
        Explicit baseline encoding; default UTF-8, without guessing.
    require_connected, require_terminal_routes : bool, optional
        Same final-network acceptance gates as preview_section_patches.

    Returns
    -------
    SectionPatchResult
        Published bytes, completion audit and both comparisons.

    Notes
    -----
    All destinations must be absent and their parents must exist. Publication
    never overwrites files. A completion audit and matching candidate hash are
    required: a process interruption can leave an incomplete transaction. On
    caught errors this function removes only files it successfully created.
    """
    source, output, audit_path = (Path(path).resolve() for path in (source_path, output_path, audit_path))
    directory = Path(report_directory).resolve() if report_directory is not None else output.parent
    for prefix in (preview_prefix, written_prefix):
        if not prefix or Path(prefix).name != prefix or any(char in prefix for char in "/\\:") or prefix in {".", ".."}:
            raise ValueError("Report prefixes must be simple filename stems")
    destinations = [output, audit_path, *(directory / f"{prefix}.{extension}" for prefix in (preview_prefix, written_prefix) for extension in ("json", "csv", "html"))]
    if len(set(destinations + [source])) != len(destinations) + 1:
        raise ValueError("Source, candidate, audit and all report paths must differ")
    for path in destinations:
        if path.exists():
            raise FileExistsError(path)
        if not path.parent.is_dir():
            raise FileNotFoundError(path.parent)
    document = read_document(source, encoding=encoding)
    # Snapshot instructions, including nested metadata, before any publication.
    frozen_list = []
    for patch in patches:
        if isinstance(patch.lines, (str, bytes)):
            raise ValueError("lines must be a sequence of individual body lines")
        frozen_list.append(SectionPatch(patch.section, tuple(patch.lines), patch.source_key, patch.basis,
                                        _json_copy(dict(patch.object_evidence)), patch.delete))
    frozen = tuple(frozen_list)
    result = preview_section_patches(document, frozen, baseline_sha256=baseline_sha256,
                                     require_connected=require_connected, require_terminal_routes=require_terminal_routes)
    stage = _stage_file(output, result.data)
    created: list[Path] = []
    audit_stage: Path | None = None
    try:
        staged = read_document(stage, encoding=encoding)
        if staged.data != result.data:
            raise ValueError("Staged candidate readback mismatch")
        created.extend(write_diff_reports(result.diff, directory, prefix=preview_prefix).values())
        if source.read_bytes() != document.data:
            raise ValueError("Source changed during publication")
        _publish_file(stage, output)
        created.append(output)
        written = compare_written_sections(document, read_document(output, encoding=encoding), frozen,
                                           baseline_sha256=baseline_sha256, require_connected=require_connected,
                                           require_terminal_routes=require_terminal_routes)
        if not written.report["verification"]["matches_expected"]:
            raise ValueError("Published candidate differs from independently replayed section patches")
        created.extend(write_diff_reports(written, directory, prefix=written_prefix).values())
        if source.read_bytes() != document.data:
            raise ValueError("Source changed during publication")
        audit = {**result.audit, "status": "published", "verification": written.report["verification"],
                 "reports": {"directory": str(directory), "preview_prefix": preview_prefix, "written_prefix": written_prefix}}
        audit_stage = _stage_file(audit_path, (json.dumps(audit, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
        _publish_file(audit_stage, audit_path)
        created.append(audit_path)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise
    finally:
        stage.unlink(missing_ok=True)
        if audit_stage is not None:
            audit_stage.unlink(missing_ok=True)
    return SectionPatchResult(result.data, audit, result.diff, written)
