"""Serialize explicit ordered interior link vertices without hydraulic inference.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained. hymo reads map geometry; SHMM writes it. EPA
SWMM 5.2 Appendix D.3 defines inlet-to-outlet interior XY rows. Map coordinates
do not establish hydraulic length, elevation, datum, or a coordinate system.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping, Sequence

from hymo.document import SWMMDocument, SWMMRecord
from hymo.geometry import read_vertices
from hymo.schemas import interpret_fields

NUMBER_PATTERN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


@dataclass(frozen=True)
class VertexChange:
    """Add one finished set of interior map vertices to a link.

    Parameters
    ----------
    object_id : str
        Existing or same-batch new link ID, compared with ASCII case folding.
    vertices : Sequence[tuple[float, float]]
        Interior XY pairs ordered from inlet to outlet, in the model's map
        coordinate system. Exclude the node endpoints. Empty means a straight
        link and writes no rows. No reprojection, reordering, or Z inference.
    source_key : str
        Caller-owned instruction key recorded in the audit.
    action : str
        Only ``add`` is supported. A link with existing vertices is rejected.

    Notes
    -----
    Values are copied to immutable tuples at construction. Existing vertex
    sets are never silently appended to or replaced. Geometry is independent
    of hydraulic length and the coordinates do not supply elevation.
    """

    object_id: str
    vertices: Sequence[tuple[float, float]]
    source_key: str
    action: str = "add"

    def __post_init__(self) -> None:
        """Freeze caller-owned point containers without changing their values."""
        if isinstance(self.vertices, (str, bytes)) or not isinstance(self.vertices, Sequence):
            raise ValueError("Vertices must be an ordered sequence of XY pairs")
        try:
            if any(isinstance(point, (str, bytes)) or not isinstance(point, Sequence) for point in self.vertices):
                raise ValueError("Vertices must be an ordered sequence of XY pairs")
            frozen = tuple(tuple(point) for point in self.vertices)
        except TypeError as exc:
            raise ValueError("Vertices must be an ordered sequence of XY pairs") from exc
        object.__setattr__(self, "vertices", frozen)


def _ascii_key(identifier: str) -> str:
    """Match the solver's ASCII case-insensitive object identity."""
    return identifier.translate(str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


def _coordinate(value: Any) -> tuple[str, float]:
    """Return a finite numeric map token and its interpreted value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Vertex coordinates must be finite numeric XY values, never booleans")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError("Vertex coordinates must be finite numeric XY values") from exc
    if not math.isfinite(number):
        raise ValueError("Vertex coordinates must be finite numeric XY values")
    return str(value), number


def prepare_vertices(
    document: SWMMDocument, changes: Sequence[VertexChange],
) -> tuple[list[str], list[dict[str, Any]]]:
    """Validate add instructions and prepare lines and per-link audit rows.

    Parameters
    ----------
    document : SWMMDocument
        Immutable original document, used to reject existing vertex sets.
    changes : Sequence[VertexChange]
        Finished interior XY instructions.

    Returns
    -------
    tuple[list[str], list[dict[str, Any]]]
        Ordered serialized rows and audits. Final link-reference and readback
        checks belong to the combined editing transaction.

    Raises
    ------
    ValueError
        Malformed IDs, missing keys, nonfinite/invalid XY, existing sets, or
        duplicate instructions for one link.
    NotImplementedError
        Replacement, append, deletion, or other actions are requested.
    """
    rows: list[str] = []
    audit: list[dict[str, Any]] = []
    seen: set[str] = set()
    for change in changes:
        if change.action != "add":
            raise NotImplementedError("STUB_VERTEX_REPLACEMENT: only vertex-set additions are supported")
        identifier = change.object_id
        if (not isinstance(identifier, str) or not identifier or not identifier.isascii()
                or len(identifier) > 31 or any(char.isspace() or ord(char) < 32 or ord(char) == 127
                                             or char in ';"[]' for char in identifier)):
            raise ValueError("Vertex link IDs must be ASCII SWMM tokens of at most 31 characters")
        if not isinstance(change.source_key, str) or not change.source_key.strip():
            raise ValueError("An explicit source_key is required")
        identity = _ascii_key(identifier)
        if identity in seen:
            raise ValueError(f"Conflicting vertex instructions for {identifier}")
        seen.add(identity)
        if read_vertices(document, identifier):
            raise ValueError(f"[VERTICES] {identifier}: addition already exists")
        points: list[list[float]] = []
        for point in change.vertices:
            if len(point) != 2:
                raise ValueError(f"[VERTICES] {identifier}: each interior vertex requires exactly XY")
            x_token, x_value = _coordinate(point[0])
            y_token, y_value = _coordinate(point[1])
            rows.append(f"{identifier} {x_token} {y_token}{document.newline}")
            points.append([x_value, y_value])
        audit.append({"action": "add", "section": "VERTICES", "object_id": identifier,
                      "source_key": change.source_key, "before": [], "after": points,
                      "fields": ["vertices"], "changed": bool(points)})
    return rows, audit


def verify_vertices(document: SWMMDocument, audit: Sequence[dict[str, Any]],
                    links: Mapping[str, SWMMRecord]) -> None:
    """Verify final link existence and exact ordered numeric readback.

    Parameters
    ----------
    document : SWMMDocument
        Final candidate read by hymo.
    audit : Sequence[dict[str, Any]]
        Per-link geometry rows produced by ``prepare_vertices``.
    links : Mapping[str, SWMMRecord]
        Final link namespace in ASCII uppercase, including same-batch additions.

    Raises
    ------
    ValueError
        A link is missing or serialized vertices differ in value or order.
    """
    coordinates: dict[str, SWMMRecord] = {}
    for record in document.records("COORDINATES"):
        identity = _ascii_key(record.tokens[0])
        if identity in coordinates:
            raise ValueError(f"[COORDINATES] duplicate ID {record.tokens[0]!r}")
        coordinates[identity] = record
    for row in audit:
        identifier = row["object_id"]
        if _ascii_key(identifier) not in links:
            raise ValueError(f"[VERTICES] {identifier}: missing link")
        link = links[_ascii_key(identifier)]
        if len(link.tokens) < 3:
            raise ValueError(f"[VERTICES] {identifier}: incomplete target link record")
        for endpoint in link.tokens[1:3]:
            coordinate_record = coordinates.get(_ascii_key(endpoint))
            if coordinate_record is None:
                raise ValueError(f"[VERTICES] {identifier}: endpoint {endpoint} requires COORDINATES")
            values = interpret_fields("COORDINATES", coordinate_record)
            for axis in ("x", "y"):
                if NUMBER_PATTERN.fullmatch(values[axis]) is None:
                    raise ValueError(f"[VERTICES] {identifier}: endpoint {endpoint} requires finite COORDINATES")
                try:
                    value = float(values[axis])
                except (ValueError, OverflowError) as exc:
                    raise ValueError(f"[VERTICES] {identifier}: endpoint {endpoint} requires finite COORDINATES") from exc
                if not math.isfinite(value):
                    raise ValueError(f"[VERTICES] {identifier}: endpoint {endpoint} requires finite COORDINATES")
        observed = read_vertices(document, identifier)
        if observed != tuple(tuple(point) for point in row["after"]):
            raise ValueError(f"[VERTICES] {identifier}: candidate readback disagrees with the edit audit")
