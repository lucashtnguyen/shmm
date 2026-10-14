"""Compare prepared edits and written models for manual engineering review.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-14
Notes: Manually maintained. Interpret source data upstream; compare model effects
here. Lexical fallback is explicit and does not imply complete SWMM semantics.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from difflib import SequenceMatcher, unified_diff
from hashlib import sha256
import html
import io
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from hymo.document import SWMMDocument, SWMMRecord
from hymo.schemas import FIELDS, interpret_fields

from .editing import Change, _equal, _key, _publish_file, _stage_file, preview_changes
from .geometry import VertexChange


@dataclass(frozen=True)
class ModelDiff:
    """Candidate bytes and JSON-compatible manual QA report; no publication.

    Parameters
    ----------
    candidate_data : bytes
        Exact proposed or actually observed candidate file content.
    report : mapping
        Versioned comparison, requests, evidence and preservation checks.
    """

    candidate_data: bytes
    report: Mapping[str, Any]


def _hash(document: SWMMDocument) -> str:
    """Identify the exact model, including comments and line endings."""
    return sha256(document.data).hexdigest()


def _text_diff(before: SWMMDocument, after: SWMMDocument, label: str) -> str:
    """Show every decoded line change, including uninterpreted source text."""
    return "".join(unified_diff(before.lines, after.lines, fromfile="baseline", tofile=label))


def _index(records: Sequence[SWMMRecord]) -> dict[str, SWMMRecord] | None:
    """Use unique ASCII-folded IDs only; never silently collapse repetitions."""
    indexed: dict[str, SWMMRecord] = {}
    for record in records:
        identity = _key(record.tokens[0])
        if identity in indexed:
            return None
        indexed[identity] = record
    return indexed


def _units(document: SWMMDocument, section: str, name: str) -> str:
    """Label verified fields without inferring a datum or map projection."""
    options = {row.tokens[0].upper(): row.tokens[1].upper()
               for row in document.records("OPTIONS") if len(row.tokens) == 2}
    flow = options.get("FLOW_UNITS", "unspecified")
    length = "ft" if flow in {"CFS", "GPM", "MGD"} else "m" if flow in {"CMS", "LPS", "MLD"} else "model length unit (unspecified)"
    if section in {"COORDINATES", "VERTICES"}:
        setting = next((row.tokens[1] for row in document.records("MAP")
                        if len(row.tokens) == 2 and row.tokens[0].upper() == "UNITS"), None)
        return f"map XY ({setting or 'units unspecified'})"
    if name in {"invert_elevation", "max_depth", "initial_depth", "surcharge_depth", "length", "inlet_offset", "outlet_offset", "geom1"}:
        return length
    if name == "ponded_area":
        return f"{length} squared"
    if name in {"initial_flow", "max_flow"}:
        return flow
    if name == "roughness":
        return "model roughness coefficient (formula dependent)"
    if name in {"geom2", "geom3", "geom4"}:
        return "shape dependent"
    return ""


def _row(section: str, object_id: str, field: str, before: Any, after: Any,
         strategy: str, baseline_line: int | None, candidate_line: int | None,
         units: str = "") -> dict[str, Any]:
    """Create one effect row; source lines are one based."""
    return {"section": section, "object_id": object_id, "field": field,
            "action": "add" if before is None else "remove" if after is None else "update",
            "before": before, "after": after, "units": units,
            "matching_strategy": strategy, "baseline_line": baseline_line,
            "candidate_line": candidate_line}


def _lexical_rows(section: str, before: Sequence[SWMMRecord], after: Sequence[SWMMRecord]) -> list[dict[str, Any]]:
    """Compare complete ordered token rows, including repeated IDs and controls."""
    rows: list[dict[str, Any]] = []
    left, right = [row.tokens for row in before], [row.tokens for row in after]
    for tag, i, j, k, l in SequenceMatcher(a=left, b=right, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        # No pairing is invented for unsupported grammars. Removal/addition
        # explicitly identifies each occurrence and keeps all repeated rows.
        for record in before[i:j]:
            rows.append(_row(section, record.tokens[0], "tokens", list(record.tokens), None,
                             "ordered lexical rows", record.line_index + 1, None))
        for record in after[k:l]:
            rows.append(_row(section, record.tokens[0], "tokens", None, list(record.tokens),
                             "ordered lexical rows", None, record.line_index + 1))
    return rows


def _effects(baseline: SWMMDocument, candidate: SWMMDocument) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Compare every section using verified fields or an honest lexical fallback."""
    rows: list[dict[str, Any]] = []
    coverage: dict[str, str] = {}
    for section in dict.fromkeys((*baseline.sections, *candidate.sections)):
        before, after = baseline.records(section), candidate.records(section)
        left, right = _index(before), _index(after)
        if section == "VERTICES":
            coverage[section] = "ordered XY rows per link; lexical coordinates"
            groups: list[dict[str, list[SWMMRecord]]] = []
            for records in (before, after):
                group: dict[str, list[SWMMRecord]] = {}
                for record in records:
                    group.setdefault(_key(record.tokens[0]), []).append(record)
                groups.append(group)
            for identity in dict.fromkeys((*groups[0], *groups[1])):
                old, new = groups[0].get(identity, []), groups[1].get(identity, [])
                old_values, new_values = [list(row.tokens[1:]) for row in old], [list(row.tokens[1:]) for row in new]
                if old_values != new_values:
                    row = (new or old)[0]
                    rows.append(_row(section, row.tokens[0], "vertices", old_values or None,
                                     new_values or None, coverage[section], old[0].line_index + 1 if old else None,
                                     new[0].line_index + 1 if new else None, _units(candidate, section, "vertices")))
            continue
        if section not in FIELDS or left is None or right is None:
            coverage[section] = "ordered lexical rows (no verified field matching)"
            rows.extend(_lexical_rows(section, before, after))
            continue
        try:
            old_fields = {key: interpret_fields(section, value) for key, value in left.items()}
            new_fields = {key: interpret_fields(section, value) for key, value in right.items()}
        except ValueError:
            coverage[section] = "ordered lexical rows (malformed supported record)"
            rows.extend(_lexical_rows(section, before, after))
            continue
        coverage[section] = "unique ASCII-case-insensitive ID; named fields"
        for identity in dict.fromkeys((*left, *right)):
            old, new = left.get(identity), right.get(identity)
            names = FIELDS[section]
            for name in names:
                previous = old_fields[identity][name] if old else None
                observed = new_fields[identity][name] if new else None
                if previous is None or observed is None or not _equal(previous, observed, name):
                    row = new or old
                    assert row is not None
                    rows.append(_row(section, row.tokens[0], name, previous, observed, coverage[section],
                                     old.line_index + 1 if old else None, new.line_index + 1 if new else None,
                                     _units(candidate, section, name)))
            # Extra lexical tails are opaque, even on otherwise understood cards.
            old_tail = list(old.tokens[len(names) + 1:]) if old else []
            new_tail = list(new.tokens[len(names) + 1:]) if new else []
            if old_tail != new_tail:
                row = new or old
                assert row is not None
                rows.append(_row(section, row.tokens[0], "opaque_tail", old_tail or None, new_tail or None,
                                 "ordered lexical tail", old.line_index + 1 if old else None,
                                 new.line_index + 1 if new else None))
    return rows, coverage


def _build_report(baseline: SWMMDocument, candidate: SWMMDocument, expected: SWMMDocument,
                  audit: Mapping[str, Any], evidence: Mapping[str, Any] | None,
                  stage: str) -> ModelDiff:
    """Join observed effects to instruction keys and compare exact expected bytes."""
    metadata = json.loads(json.dumps(dict(evidence or {}), allow_nan=False))
    requests = []
    for instruction in audit["changes"]:
        requests.append({**instruction, "evidence": metadata.get(instruction["source_key"], {}),
                         "field_units": {name: _units(expected, instruction["section"], name)
                                         for name in instruction["fields"]}})
    rows, coverage = _effects(baseline, candidate)
    expected_rows, _ = _effects(baseline, expected)
    expected_effects = {(row["section"], _key(row["object_id"]), row["field"]): row for row in expected_rows}
    observed_keys = set()
    for row in rows:
        key = row["section"], _key(row["object_id"]), row["field"]
        observed_keys.add(key)
        expected_row = expected_effects.get(key)
        row["reconciliation"] = ("requested_effect" if expected_row and row["before"] == expected_row["before"] and row["after"] == expected_row["after"]
                                 else "unexpected_effect")
        matching = [request for request in requests if request["section"] == row["section"] and _key(request["object_id"]) == key[1]
                    and (request["action"] == "add" or row["field"] in request["fields"])]
        row["source_keys"] = [request["source_key"] for request in matching]
        row["evidence"] = [request["evidence"] for request in matching]
    missing = [row for key, row in expected_effects.items() if key not in observed_keys]
    for row in missing:
        matching = [request for request in requests if request["section"] == row["section"]
                    and _key(request["object_id"]) == _key(row["object_id"])
                    and (request["action"] == "add" or row["field"] in request["fields"])]
        row.update(reconciliation="missing_effect", source_keys=[request["source_key"] for request in matching],
                   evidence=[request["evidence"] for request in matching])
    matches = candidate.data == expected.data
    report = {"schema_version": "1", "stage": stage,
              "baseline_sha256": _hash(baseline), "candidate_sha256": _hash(candidate),
              "expected_candidate_sha256": _hash(expected), "requested_operations": requests,
              "effects": rows, "missing_expected_effects": missing,
              "verification": {"matches_expected": matches, "exact_bytes_checked": True,
                               "unexpected_effects": sum(row["reconciliation"] == "unexpected_effect" for row in rows),
                               "missing_effects": len(missing),
                               "requested_noops": sum(not request["changed"] for request in requests)},
              "section_matching": coverage,
              "raw_text_diff": _text_diff(baseline, candidate, "candidate"),
              "unexpected_text_diff": _text_diff(expected, candidate, "written candidate") if not matches else "",
              "limits": ["Only supported named fields have semantic comparison; other cards use ordered lexical rows.",
                         "Raw text and exact bytes include comments, headers, ordering, whitespace and opaque content.",
                         "No GIS interpretation, datum resolution, hydraulic simulation or engineering acceptance."]}
    return ModelDiff(candidate.data, report)


def preview_model_diff(document: SWMMDocument, changes: Sequence[Change], *,
                       vertex_changes: Sequence[VertexChange] = (), evidence: Mapping[str, Any] | None = None,
                       expected_hash: str | None = None) -> ModelDiff:
    """Preview baseline-to-proposed effects and upstream evidence without writing.

    Parameters
    ----------
    document : SWMMDocument
        Immutable baseline read by hymo.
    changes, vertex_changes : sequence
        Finished SHMM instructions in baseline units and map coordinates.
    evidence : mapping, optional
        JSON metadata keyed by instruction source_key; preserved without engineering interpretation.
    expected_hash : str, optional
        Required baseline SHA-256 precondition when supplied.

    Returns
    -------
    ModelDiff
        Candidate bytes and requested operations, actual effects, hashes and raw diff.
    """
    result = preview_changes(document, changes, vertex_changes=vertex_changes, expected_hash=expected_hash)
    candidate = SWMMDocument.from_bytes(result.data, encoding=document.encoding)
    return _build_report(document, candidate, candidate, result.audit, evidence, "preview")


def compare_written_model(baseline: SWMMDocument, candidate: SWMMDocument, changes: Sequence[Change], *,
                          vertex_changes: Sequence[VertexChange] = (), evidence: Mapping[str, Any] | None = None,
                          expected_hash: str | None = None) -> ModelDiff:
    """Compare a re-read candidate against baseline and independently replayed requests.

    Parameters
    ----------
    baseline, candidate : SWMMDocument
        Read the actual published candidate with hymo, not from preview memory.
    changes, vertex_changes : sequence
        The same finished instructions supplied for publication.
    evidence : mapping, optional
        JSON upstream source references, basis, units and QA flags keyed by source_key.
    expected_hash : str, optional
        SHA-256 baseline precondition.

    Returns
    -------
    ModelDiff
        ``report['verification']['matches_expected']`` is true only for exact
        byte equality with the requested candidate, including opaque text.
        A mismatch is reported for review rather than hidden or auto-corrected.
    """
    result = preview_changes(baseline, changes, vertex_changes=vertex_changes, expected_hash=expected_hash)
    expected = SWMMDocument.from_bytes(result.data, encoding=baseline.encoding)
    return _build_report(baseline, candidate, expected, result.audit, evidence, "written_model")


def _cell(value: Any) -> str:
    """Encode structured values for CSV and protect formula-looking cell text."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + text
    return text


def _render_html(report: Mapping[str, Any]) -> str:
    """Build a standalone escaped report with searchable effects and requests."""
    rows = []
    for category, records in (("effect", report["effects"]), ("missing_effect", report["missing_expected_effects"]),
                              ("request", report["requested_operations"])):
        for row in records:
            values = [category, row.get("section"), row.get("object_id"), row.get("field", row.get("fields")),
                      row.get("action"), row.get("before"), row.get("after"), row.get("units", row.get("field_units", "")),
                      row.get("reconciliation", "changed" if row.get("changed") else "no-op"),
                      row.get("source_keys", row.get("source_key")), row.get("evidence")]
            rows.append("<tr>" + "".join(f"<td>{html.escape(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))}</td>" for value in values) + "</tr>")
    summary = {key: report[key] for key in ("stage", "baseline_sha256", "candidate_sha256", "expected_candidate_sha256", "verification", "section_matching", "limits")}
    return ("<!doctype html><html lang='en'><meta charset='utf-8'><title>SHMM model change review</title>"
            "<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:6px;text-align:left;vertical-align:top}th{background:#eee}pre{white-space:pre-wrap;overflow-wrap:anywhere}input{width:60%;padding:8px}td{overflow-wrap:anywhere;max-width:400px}</style>"
            "<h1>SHMM model change review</h1><p>Review requested operations (including no-ops), observed effects, source evidence and QA flags. Exact-byte verification is separate from engineering acceptance.</p>"
            f"<pre>{html.escape(json.dumps(summary, indent=2, ensure_ascii=False))}</pre>"
            "<label>Filter rows <input id='filter' placeholder='ID, section, field, source key, QA flag or evidence'></label>"
            "<table><thead><tr>" + "".join(f"<th>{name}</th>" for name in ("Kind", "Section", "Object", "Field", "Action", "Before", "After", "Units", "Status", "Source", "Evidence")) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
            f"<h2>Missing expected effects</h2><pre>{html.escape(json.dumps(report['missing_expected_effects'], indent=2))}</pre>"
            f"<h2>Baseline to candidate text</h2><pre>{html.escape(report['raw_text_diff'])}</pre>"
            f"<h2>Unexpected written text</h2><pre>{html.escape(report['unexpected_text_diff'])}</pre>"
            "<script>document.getElementById('filter').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>")


def write_diff_reports(diff: ModelDiff, output_directory: str | Path, *, prefix: str = "model_diff") -> dict[str, Path]:
    """Publish JSON, CSV and standalone filterable HTML without overwriting files.

    Parameters
    ----------
    diff : ModelDiff
        Preview or written-model report.
    output_directory : str or Path
        Existing directory; project data and reports belong outside public repos.
    prefix : str, optional
        Simple filename prefix, such as preview_diff or written_model_diff.

    Returns
    -------
    dict of str to Path
        Published json/csv/html files. JSON is the lossless machine contract;
        CSV includes effects and requested operations with searchable evidence.

    Notes
    -----
    No map/profile renderer is provided yet. Compare elevations and geometry in
    the tables and model viewer. CSV formula-leading text is apostrophe escaped.
    """
    directory = Path(output_directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    if not prefix or Path(prefix).name != prefix or any(char in prefix for char in '/\\:') or prefix in {".", ".."}:
        raise ValueError("prefix must be a simple filename stem")
    report = diff.report
    stream = io.StringIO(newline="")
    columns = ["kind", "section", "object_id", "field", "action", "before", "after", "units", "reconciliation", "source_keys", "evidence"]
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for kind, records in (("effect", report["effects"]), ("missing_effect", report["missing_expected_effects"]),
                          ("request", report["requested_operations"])):
        for record in records:
            row = {**record, "kind": kind}
            if kind == "request":
                row.update(field=record["fields"], units=record["field_units"],
                           reconciliation="changed" if record["changed"] else "no-op", source_keys=[record["source_key"]])
            writer.writerow({name: _cell(row.get(name, "")) for name in columns})
    content = {"json": (json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"),
               "csv": stream.getvalue().encode("utf-8-sig"), "html": _render_html(report).encode("utf-8")}
    paths = {extension: directory / f"{prefix}.{extension}" for extension in content}
    for path in paths.values():
        if path.exists():
            raise FileExistsError(path)
    stages: list[Path] = []
    published: list[Path] = []
    try:
        for extension, data in content.items():
            stage = _stage_file(paths[extension], data)
            stages.append(stage)
            _publish_file(stage, paths[extension])
            published.append(paths[extension])
    except BaseException:
        for path in published:
            path.unlink(missing_ok=True)
        raise
    finally:
        for stage in stages:
            stage.unlink(missing_ok=True)
    return paths
