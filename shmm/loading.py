"""Validate and fingerprint loading sections of a candidate or written model.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-11-13
Notes: Manually maintained. hymo interprets the sections; this module checks a
written or previewed model's loading records before/after publication. It never
derives, scales or normalizes loads (upstream owns engineering decisions).
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any

from hymo.document import SWMMDocument
from hymo.loading import read_loading

_NODE_SECTIONS = ("JUNCTIONS", "STORAGE", "OUTFALLS", "DIVIDERS")


def _finite(value: str) -> bool:
    try:
        return Decimal(value).is_finite()
    except (InvalidOperation, TypeError):
        return False


def validate_loading(document: SWMMDocument) -> dict[str, Any]:
    """Check loading rows, references and duplicates in a SWMM document.

    Parameters
    ----------
    document : SWMMDocument
        Previewed or re-read written model.

    Returns
    -------
    dict
        ``passed``, ``issues`` (machine-readable strings), ``warnings`` and row
        counts. Issues: hymo interpretation problems (missing pattern/series,
        malformed rows, wrong pattern lengths), non-finite quantities, negative
        RDII areas, rows on undeclared nodes, duplicate node/constituent rows in
        DWF or INFLOWS and a missing FLOW_UNITS option. Warnings: negative flow
        quantities and pattern multipliers (allowed by SWMM, but unusual), FLOW
        units factors other than one, external FILE series (not read) and
        non-empty tokens after the last field SWMM reads (the row is applied by
        the engine and kept; the extra token is ignored).

    Notes
    -----
    A duplicate node/constituent row fails because the engine applies only the
    last such row, so an earlier row's flow would be lost silently; a writer
    must give each node at most one FLOW row per section. A row with extra
    trailing tokens only warns, because the engine applies it in full.
    ``record_counts`` (raw records) is reported beside ``counts`` (typed rows).
    """
    inventory = read_loading(document)
    issues = list(inventory.issues)
    warnings = [note.split(":ignored_extra_tokens", 1)[0] + ":ignored_extra_tokens" for note in inventory.notes]
    nodes = {r.tokens[0].upper() for name in _NODE_SECTIONS for r in document.records(name)}
    if inventory.flow_units is None:
        issues.append("OPTIONS:FLOW_UNITS:missing")
    for section, rows in (("DWF", inventory.dwf), ("INFLOWS", inventory.inflows), ("RDII", inventory.rdii)):
        for row in rows:
            if row.node.upper() not in nodes:
                issues.append(f"{section}:{row.node}:undeclared_node")
    for row in inventory.dwf:
        if not _finite(row.average):
            issues.append(f"DWF:{row.node}:nonfinite_average")
        elif Decimal(row.average) < 0:
            warnings.append(f"DWF:{row.node}:negative_average")
    for row in inventory.inflows:
        for label, value in (("units_factor", row.units_factor), ("scale_factor", row.scale_factor), ("baseline", row.baseline)):
            if not _finite(value):
                issues.append(f"INFLOWS:{row.node}:nonfinite_{label}")
        if row.is_flow and _finite(row.units_factor) and Decimal(row.units_factor) != 1:
            warnings.append(f"INFLOWS:{row.node}:flow_units_factor_not_one")
        if row.is_flow and _finite(row.baseline) and Decimal(row.baseline) < 0:
            warnings.append(f"INFLOWS:{row.node}:negative_baseline")
    for row in inventory.rdii:
        if not _finite(row.sewer_area):
            issues.append(f"RDII:{row.node}:nonfinite_area")
        elif Decimal(row.sewer_area) < 0:
            issues.append(f"RDII:{row.node}:negative_area")
    for section, rows in (("DWF", inventory.dwf), ("INFLOWS", inventory.inflows)):
        counts = Counter((row.node.upper(), row.constituent.upper()) for row in rows)
        issues.extend(f"{section}:{node}:{constituent}:duplicate_row" for (node, constituent), n in sorted(counts.items()) if n > 1)
    counts = Counter(row.node.upper() for row in inventory.rdii)
    issues.extend(f"RDII:{node}:duplicate_row" for node, n in sorted(counts.items()) if n > 1)
    for pattern in inventory.patterns.values():
        for value in pattern.multipliers:
            if not _finite(value):
                issues.append(f"PATTERNS:{pattern.name}:nonfinite_multiplier"); break
            if Decimal(value) < 0:
                warnings.append(f"PATTERNS:{pattern.name}:negative_multiplier"); break
    for series in inventory.timeseries.values():
        if series.file is not None:
            warnings.append(f"TIMESERIES:{series.name}:external_file_not_read")
        for _, _, value in series.points:
            if not _finite(value):
                issues.append(f"TIMESERIES:{series.name}:nonfinite_value"); break
    return {"passed": not issues, "issues": sorted(set(issues)), "warnings": sorted(set(warnings)),
            "flow_units": inventory.flow_units, "record_counts": dict(inventory.record_counts),
            "counts": {"DWF": len(inventory.dwf), "INFLOWS": len(inventory.inflows), "RDII": len(inventory.rdii),
                       "PATTERNS": len(inventory.patterns), "TIMESERIES": len(inventory.timeseries)}}


def loading_fingerprint(document: SWMMDocument) -> str:
    """Hash loading semantics (rows and definitions), ignoring comments and order.

    Identical fingerprints mean the interpreted DWF/INFLOWS/RDII rows and the
    PATTERNS/TIMESERIES definitions are token-identical (case-folded IDs), so a
    written model can be checked against its preview or a regression baseline
    without depending on comment text or row order.
    """
    inventory = read_loading(document)
    payload = {
        "flow_units": inventory.flow_units,
        "dwf": sorted([r.node.upper(), r.constituent.upper(), r.average, *(p.upper() for p in r.patterns)] for r in inventory.dwf),
        "inflows": sorted([r.node.upper(), r.constituent.upper(), r.timeseries.upper(), r.type.upper(), r.units_factor,
                           r.scale_factor, r.baseline, r.baseline_pattern.upper()] for r in inventory.inflows),
        "rdii": sorted([r.node.upper(), r.unit_hydrograph.upper(), r.sewer_area] for r in inventory.rdii),
        "patterns": sorted([p.name.upper(), p.type, *p.multipliers] for p in inventory.patterns.values()),
        "timeseries": sorted([s.name.upper(), s.file, [list(p) for p in s.points]] for s in inventory.timeseries.values()),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
