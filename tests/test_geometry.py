"""Verify ordered display geometry additions without changing hydraulics.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained synthetic fixtures; no private asset data.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from hymo import SWMMDocument, read_vertices
import pytest

from shmm import Change, VertexChange, apply_changes, edit_model, preview_changes


BASELINE = (
    b"; synthetic geometry contract\r\n"
    b"[OPTIONS]\r\nFLOW_UNITS CFS\r\n"
    b"[JUNCTIONS]\r\nN1 10 5\r\nN2 8 6\r\n"
    b"[CONDUITS]\r\nP1 N1 N2 100 0.013 0 0\r\n"
    b"[XSECTIONS]\r\nP1 CIRCULAR 1 0 0 0\r\n"
    b"[COORDINATES]\r\nN1 0 0\r\nN2 10 0\r\n"
    b"[BACKDROP]\r\n; untouched text\r\n"
)


def document(data: bytes = BASELINE) -> SWMMDocument:
    """Create the read-only baseline for one independent test."""
    return SWMMDocument.from_bytes(data)


def geometry(object_id: str = "P1", vertices: object = ((3.5, 2), (7, -1))) -> VertexChange:
    """Construct a finished synthetic interior XY instruction."""
    return VertexChange(object_id, vertices, "synthetic-geometry")


def test_interior_vertices_keep_order_and_hydraulic_values() -> None:
    """Interior rows follow caller order; length never becomes map distance."""
    result = preview_changes(document(), [], vertex_changes=[geometry()])
    assert result.data == BASELINE + b"\r\n[VERTICES]\r\nP1 3.5 2\r\nP1 7 -1\r\n"
    reread = document(result.data)
    assert read_vertices(reread, "p1") == ((3.5, 2.0), (7.0, -1.0))
    assert reread.records("CONDUITS")[0].tokens == document().records("CONDUITS")[0].tokens
    row = result.audit["changes"][0]
    assert row["section"] == "VERTICES"
    assert row["before"] == []
    assert row["after"] == [[3.5, 2.0], [7.0, -1.0]]
    assert row["changed"] is True
    assert result.audit["baseline_sha256"] == sha256(BASELINE).hexdigest()
    assert result.audit["candidate_sha256"] == sha256(result.data).hexdigest()


def test_new_link_and_vertices_share_one_transaction() -> None:
    """A link and endpoint coordinates created in the batch are valid targets."""
    changes = [
        Change("add", "JUNCTIONS", "N3", {"invert_elevation": 6, "max_depth": 4}, "node"),
        Change("add", "COORDINATES", "N3", {"x": 20, "y": 5}, "node-map"),
        Change("add", "CONDUITS", "P2", {"inlet_node": "N2", "outlet_node": "N3",
              "length": 50, "roughness": 0.014, "inlet_offset": 0, "outlet_offset": 0}, "pipe"),
        Change("add", "XSECTIONS", "P2", {"shape": "CIRCULAR", "geom1": 0.75,
              "geom2": 0, "geom3": 0, "geom4": 0}, "section"),
    ]
    result = apply_changes(document(), changes, vertex_changes=[geometry("p2", ((15, 4),))])
    assert read_vertices(document(result.data), "P2") == ((15.0, 4.0),)
    assert [row["section"] for row in result.audit["changes"]] == [
        "JUNCTIONS", "COORDINATES", "CONDUITS", "XSECTIONS", "VERTICES"]


def test_existing_geometry_rows_are_preserved_byte_for_byte() -> None:
    """Repeated legacy link IDs are legal and their spacing/comments survive."""
    baseline = BASELINE.replace(b"[CONDUITS]\r\n", b"[CONDUITS]\r\nP0 N1 N2 50 0.014 0 0\r\n").replace(
        b"[XSECTIONS]\r\n", b"[XSECTIONS]\r\nP0 CIRCULAR 1 0 0 0\r\n")
    vertices = b"[VERTICES]\r\n  P0\t2.500 4 ; first point\r\np0 7 -1.000 ; second\r\n"
    baseline = baseline.replace(b"[BACKDROP]", vertices + b"[BACKDROP]")
    result = apply_changes(document(baseline), [], vertex_changes=[geometry()])
    assert result.data == baseline.replace(vertices, vertices + b"P1 3.5 2\r\nP1 7 -1\r\n")
    assert read_vertices(document(result.data), "P0") == ((2.5, 4.0), (7.0, -1.0))


def test_straight_link_writes_no_vertex_section_or_rows() -> None:
    """An explicit empty set verifies a straight link and preserves all bytes."""
    result = apply_changes(document(), [], vertex_changes=[geometry(vertices=())])
    assert result.data == BASELINE
    assert result.audit["changes"][0]["after"] == []
    assert result.audit["changes"][0]["changed"] is False


@pytest.mark.parametrize("vertices", [((1,),), ((1, 2, 3),), ((True, 2),), (("1", 2),),
                                      ((float("nan"), 2),), ((1, float("inf")),), ((10**500, 1),)])
def test_invalid_or_nonfinite_xy_is_rejected(vertices: object) -> None:
    """No booleans, Z coordinates, invalid dimensions, or nonfinite values."""
    with pytest.raises(ValueError):
        apply_changes(document(), [], vertex_changes=[geometry(vertices=vertices)])


@pytest.mark.parametrize("vertices", [None, "1 2", [1, 2], {(1, 2)}, ({1, 2},), ("12",)])
def test_malformed_point_containers_are_rejected(vertices: object) -> None:
    """Scalar coordinate collections are not silently interpreted as XY."""
    with pytest.raises(ValueError):
        geometry(vertices=vertices)


def test_vertices_copy_caller_sequence() -> None:
    """Mutating input lists after construction cannot change the instruction."""
    values = [[3.5, 2], [7, -1]]
    instruction = geometry(vertices=values)
    values[0][0] = 500
    values.append([9, 9])
    assert instruction.vertices == ((3.5, 2), (7, -1))


def test_missing_link_is_rejected_even_for_straight_geometry() -> None:
    """An empty vertex set still requires an actual candidate link."""
    with pytest.raises(ValueError, match="missing link"):
        apply_changes(document(), [], vertex_changes=[geometry("missing", ())])


def test_existing_set_and_case_duplicate_instructions_are_rejected() -> None:
    """Add does not overwrite legacy geometry or accept two instructions."""
    with pytest.raises(ValueError, match="already exists"):
        apply_changes(document(BASELINE + b"[VERTICES]\r\np1 5 2\r\n"), [],
                      vertex_changes=[geometry()])
    with pytest.raises(ValueError, match="Conflicting vertex instructions"):
        apply_changes(document(), [], vertex_changes=[geometry(), geometry("p1", ())])


@pytest.mark.parametrize("identifier", ["", "A B", "A;B", "A[B]", "é", "A" * 32, 1])
def test_invalid_link_identifier_is_rejected(identifier: object) -> None:
    """IDs must be explicit safe ASCII text, retaining leading zero semantics."""
    with pytest.raises(ValueError):
        apply_changes(document(), [], vertex_changes=[geometry(identifier)])


def test_source_key_and_add_only_contract_are_explicit() -> None:
    """Deferred mutations and missing traceability fail clearly."""
    with pytest.raises(ValueError, match="source_key"):
        apply_changes(document(), [], vertex_changes=[VertexChange("P1", (), " ")])
    with pytest.raises(NotImplementedError, match="STUB_VERTEX_REPLACEMENT"):
        apply_changes(document(), [], vertex_changes=[VertexChange("P1", (), "test", "update")])


@pytest.mark.parametrize("baseline, expected", [
    (BASELINE.replace(b"N2 10 0\r\n", b""), "requires COORDINATES"),
    (BASELINE.replace(b"N2 10 0", b"N2 nan 0"), "finite COORDINATES"),
    (BASELINE.replace(b"N2 10 0", b"N2 10 inf"), "finite COORDINATES"),
    (BASELINE.replace(b"N2 10 0", b"N2 1_0 0"), "finite COORDINATES"),
])
def test_target_endpoints_require_finite_coordinates(baseline: bytes, expected: str) -> None:
    """A map polyline needs both endpoint positions, including straight links."""
    with pytest.raises(ValueError, match=expected):
        apply_changes(document(baseline), [], vertex_changes=[geometry(vertices=())])


def test_malformed_legacy_vertices_fail_clearly() -> None:
    """Reading rejects ambiguous legacy rows before any candidate can publish."""
    with pytest.raises(ValueError, match="VERTICES"):
        apply_changes(document(BASELINE + b"[VERTICES]\r\nP1 1 2 3\r\n"), [],
                      vertex_changes=[geometry()])


def test_geometry_hash_precondition_and_publication(tmp_path: Path) -> None:
    """Publication audits original and final bytes without modifying baseline."""
    source = tmp_path / "baseline.inp"
    candidate = tmp_path / "candidate.inp"
    audit = tmp_path / "candidate.audit.json"
    source.write_bytes(BASELINE)
    with pytest.raises(ValueError, match="Stale baseline"):
        edit_model(source, [], candidate, audit, expected_hash="wrong", vertex_changes=[geometry()])
    assert not candidate.exists() and not audit.exists()
    result = edit_model(source, [], candidate, audit, expected_hash=sha256(BASELINE).hexdigest(),
                        vertex_changes=[geometry()])
    assert source.read_bytes() == BASELINE
    assert candidate.read_bytes() == result.data
    persisted = json.loads(audit.read_text())
    assert persisted["baseline_sha256"] == sha256(BASELINE).hexdigest()
    assert persisted["candidate_sha256"] == sha256(candidate.read_bytes()).hexdigest()
    assert str(tmp_path) not in audit.read_text()


def test_invalid_combined_transaction_publishes_nothing(tmp_path: Path) -> None:
    """A late geometry failure cannot publish earlier valid hydraulic edits."""
    source = tmp_path / "baseline.inp"
    candidate = tmp_path / "candidate.inp"
    audit = tmp_path / "candidate.audit.json"
    source.write_bytes(BASELINE)
    changes = [Change("update", "CONDUITS", "P1", {"length": 150}, "length")]
    with pytest.raises(ValueError, match="missing link"):
        edit_model(source, changes, candidate, audit, vertex_changes=[geometry("missing")])
    assert source.read_bytes() == BASELINE
    assert not candidate.exists() and not audit.exists()
