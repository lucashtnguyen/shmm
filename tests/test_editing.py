"""Verify explicit SWMM editing, source preservation, and safe publication.

Author: Lucas HT Nguyen
Last modified by: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-15
Manually maintained synthetic contract cases; no private project data.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from hymo import SWMMDocument, read_document
from shmm import Change, apply_changes, edit_model, preview_changes
import shmm.editing as editing


BASELINE = (
    b"; Synthetic engineering contract fixture\r\n"
    b"[OPTIONS]\r\nFLOW_UNITS CFS\r\nLINK_OFFSETS DEPTH\r\n"
    b"[JUNCTIONS]\r\nN1 10 5\r\nN2 8 6\r\n"
    b"[OUTFALLS]\r\nO1 0 FREE NO\r\n"
    b"[CONDUITS]\r\n  P1\tN1 N2 100.000 0.013 0 0 ; retained pipe note\r\n"
    b"[XSECTIONS]\r\nP1 CIRCULAR 1 0 0 0\r\n"
    b"[DWF]\r\nN1 FLOW 0.25\r\nN1 TSS 10\r\n"
    b"[INFLOWS]\r\nN2 FLOW TS1 FLOW 1 1 0\r\n"
    b"[RDII]\r\nN1 UH1 1\r\n"
    b"[CURVES]\r\nC1 PUMP1 0 0\r\nC1 1 2\r\n"
    b"[TIMESERIES]\r\nTS1 01/01/2020 00:00 0\r\n"
    b"[BACKDROP]\nkeep this exact unknown tail"
)


def change(
    section: str = "CONDUITS", object_id: str = "P1", *,
    action: str = "update", expected: dict[str, object] | None = None,
    source_key: str = "synthetic-operation", **values: object,
) -> Change:
    """Build explicit synthetic instructions without inferred values."""
    return Change(action, section, object_id, values, source_key, expected or {})


def document(data: bytes = BASELINE, *, encoding: str = "utf-8") -> SWMMDocument:
    """Return an independent immutable reader object for a test."""
    return SWMMDocument.from_bytes(data, encoding=encoding)


def addition_batch() -> list[Change]:
    """Supply every required engineering quantity for a new branch."""
    return [
        change("JUNCTIONS", "N3", action="add", invert_elevation=7, max_depth=4),
        change("CONDUITS", "P2", action="add", inlet_node="N2", outlet_node="N3",
               length=50, roughness=0.014, inlet_offset=0, outlet_offset=0),
        change("XSECTIONS", "P2", action="add", shape="CIRCULAR", geom1=0.75,
               geom2=0, geom3=0, geom4=0),
        change("COORDINATES", "N3", action="add", x=100, y=-25),
    ]


def test_changes_only_requested_token_spans_and_preserves_linked_loading() -> None:
    """Length and diameter edits preserve hydraulic inputs outside those fields."""
    original = document()
    result = apply_changes(original, [change(length=125), change("XSECTIONS", geom1=1.5)])
    expected = BASELINE.replace(b"100.000 0.013", b"125 0.013").replace(
        b"P1 CIRCULAR 1 0", b"P1 CIRCULAR 1.5 0"
    )
    assert result.data == expected
    assert original.data == BASELINE
    reread = document(result.data)
    for section in ("DWF", "INFLOWS", "RDII", "CURVES", "TIMESERIES", "BACKDROP"):
        assert reread.records(section) == original.records(section)
    assert [row["fields"] for row in result.audit["changes"]] == [["length"], ["geom1"]]
    assert result.audit["changes"][0]["before"]["length"] == "100.000"
    assert result.audit["changes"][0]["after"]["length"] == "125"


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252"])
def test_no_operation_preserves_every_byte_and_unsupported_sections(encoding: str) -> None:
    """No-op behavior includes encodings whose encoder can insert a BOM."""
    result = preview_changes(document(encoding=encoding), [])
    assert result.data == BASELINE
    assert result.audit["changes"] == []
    assert result.audit["candidate_sha256"] == sha256(BASELINE).hexdigest()
    assert "BACKDROP" in result.audit["uninterpreted_sections"]


def test_numeric_spelling_and_case_equivalence_are_true_no_ops() -> None:
    """Equivalent engineering values must not reformat original source text."""
    result = apply_changes(document(), [change(length=100, inlet_node="n1")])
    assert result.data == BASELINE
    assert result.audit["changes"][0]["changed"] is False


def test_append_missing_optional_fields_before_existing_comment() -> None:
    """A late optional value requires documented intervening defaults only."""
    result = apply_changes(document(), [change(max_flow=2.5)])
    assert result.data == BASELINE.replace(
        b"0.013 0 0 ; retained pipe note", b"0.013 0 0 0 2.5 ; retained pipe note"
    )
    assert document(result.data).records("CONDUITS")[0].tokens[-2:] == ("0", "2.5")


def test_add_supporting_nodes_pipe_xsection_and_missing_coordinate_section() -> None:
    """A complete batch can reference nodes created in that same batch."""
    original = document()
    result = apply_changes(original, addition_batch())
    reread = document(result.data)
    assert reread.records("JUNCTIONS")[-1].tokens == ("N3", "7", "4")
    assert reread.records("CONDUITS")[-1].tokens == ("P2", "N2", "N3", "50", "0.014", "0", "0")
    assert reread.records("XSECTIONS")[-1].tokens == ("P2", "CIRCULAR", "0.75", "0", "0", "0")
    assert reread.records("COORDINATES")[0].tokens == ("N3", "100", "-25")
    assert result.data.endswith(b"[COORDINATES]\r\nN3 100 -25\r\n")
    assert b"keep this exact unknown tail\r\n" in result.data
    assert original.data == BASELINE


def test_add_to_existing_coordinate_section() -> None:
    """Coordinate additions retain existing coordinates and trailing sections."""
    data = BASELINE.replace(b"[BACKDROP]", b"[COORDINATES]\r\nN1 0 0\r\n[BACKDROP]")
    result = apply_changes(document(data), addition_batch())
    assert document(result.data).records("COORDINATES")[0].tokens == ("N1", "0", "0")
    assert document(result.data).records("COORDINATES")[1].tokens == ("N3", "100", "-25")
    assert result.data.endswith(b"[BACKDROP]\nkeep this exact unknown tail")


@pytest.mark.parametrize("section,values", [
    ("CONDUITS", {"unsupported_field": 1}),
    ("CONDUITS", {"length": None}),
    ("CONDUITS", {"length": True}),
    ("CONDUITS", {"length": "nan"}),
    ("CONDUITS", {"length": "NaN"}),
    ("CONDUITS", {"length": "1_000"}),
    ("CONDUITS", {"length": "\u0661"}),
    ("CONDUITS", {"length": "100\x00"}),
    ("CONDUITS", {"length": float("inf")}),
    ("CONDUITS", {"roughness": float("-inf")}),
    ("CONDUITS", {"length": "one hundred"}),
    ("CONDUITS", {"length": "100;injected"}),
    ("CONDUITS", {"length": 0}),
    ("CONDUITS", {"length": -1}),
    ("CONDUITS", {"roughness": 0}),
    ("CONDUITS", {"max_flow": -1}),
    ("XSECTIONS", {"geom1": 0}),
    ("XSECTIONS", {"geom1": -1}),
    ("XSECTIONS", {"barrels": 0}),
    ("XSECTIONS", {"barrels": 1.5}),
    ("XSECTIONS", {"barrels": 128}),
    ("XSECTIONS", {"barrels": "1e0"}),
    ("XSECTIONS", {"culvert": -1}),
    ("XSECTIONS", {"culvert": 58}),
    ("XSECTIONS", {"culvert": "1e0"}),
])
def test_rejects_invalid_engineering_fields(section: str, values: dict[str, object]) -> None:
    """Malformed values and physically impossible touched parameters fail."""
    with pytest.raises(ValueError):
        apply_changes(document(), [change(section, **values)])


@pytest.mark.parametrize("field", ["max_depth", "initial_depth", "surcharge_depth", "ponded_area"])
def test_rejects_negative_junction_depths_and_area(field: str) -> None:
    """Depth/area bounds apply while absolute invert elevations may be negative."""
    with pytest.raises(ValueError, match="nonnegative"):
        apply_changes(document(), [change("JUNCTIONS", "N1", **{field: -1})])
    result = apply_changes(document(), [change("JUNCTIONS", "N1", invert_elevation=-2)])
    assert document(result.data).records("JUNCTIONS")[0].tokens[1] == "-2"


@pytest.mark.parametrize("offset", [-1, "*"])
def test_depth_offsets_reject_negative_or_elevation_sentinel(offset: object) -> None:
    """DEPTH offsets cannot silently become absolute elevation inputs."""
    with pytest.raises(ValueError):
        apply_changes(document(), [change(inlet_offset=offset)])


@pytest.mark.parametrize("offset", [-1, "*"])
def test_elevation_offsets_accept_negative_and_node_elevation_sentinel(offset: object) -> None:
    """Absolute elevation offsets accept below-datum values and EPA '*' behavior."""
    data = BASELINE.replace(b"LINK_OFFSETS DEPTH", b"LINK_OFFSETS ELEVATION")
    result = apply_changes(document(data), [change(inlet_offset=offset)])
    assert document(result.data).records("CONDUITS")[0].tokens[5] == str(offset)


@pytest.mark.parametrize("item,message", [
    (change("CONDUITS", "missing", length=1), "target is missing"),
    (change("CONDUITS", "p1", action="add", length=1), "already exists"),
    (change(length=1, source_key=""), "source_key"),
    (change(), "at least one field"),
    (change(length=1, expected={"length": 99}), "stale old value"),
    (change(length=1, expected={"bad_old_field": 99}), "unknown fields"),
    (change("CONDUITS", "X" * 32, length=1), "31 characters"),
    (change("CONDUITS", "invalid id", length=1), "single unquoted"),
    (change("JUNCTIONS", "N3", action="add", max_depth=2), "missing required"),
    (change("JUNCTIONS", "N3", action="add", invert_elevation=0, expected={"invert_elevation": 1}), "old-value"),
])
def test_instruction_validation(item: Change, message: str) -> None:
    """Incomplete instructions and stale preconditions fail before changes escape."""
    with pytest.raises(ValueError, match=message):
        apply_changes(document(), [item])


@pytest.mark.parametrize("identifier", [1, True, None])
def test_identifier_must_be_explicit_text(identifier: object) -> None:
    """Text IDs preserve leading zeros and prevent accidental numeric identity loss."""
    item = Change("update", "CONDUITS", identifier, {"length": 1}, "invalid-id")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        apply_changes(document(), [item])


def test_conflicting_batch_targets_reject_case_insensitively() -> None:
    """Two instructions cannot independently claim the same target record."""
    with pytest.raises(ValueError, match="Conflicting"):
        apply_changes(document(), [change(length=1), change(object_id="p1", roughness=0.02)])


@pytest.mark.parametrize("data", [
    BASELINE.replace(b"N2 8 6", b"N2 8 6\r\nn1 9 5"),
    BASELINE.replace(b"O1 0 FREE NO", b"N1 0 FREE NO"),
    BASELINE.replace(b"[XSECTIONS]", b"[PUMPS]\r\np1 N2 O1 C1\r\n[XSECTIONS]"),
])
def test_existing_duplicate_ids_within_and_across_object_namespaces(data: bytes) -> None:
    """Case-insensitive uniqueness applies across node and link type sections."""
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        apply_changes(document(data), [change(length=120)])


def test_added_node_cannot_collide_with_an_existing_outfall() -> None:
    """New junction IDs share the complete hydraulic node namespace."""
    with pytest.raises(ValueError, match="Duplicate object ID"):
        apply_changes(document(), [change("JUNCTIONS", "o1", action="add", invert_elevation=0)])


@pytest.mark.parametrize("changes,message", [
    ([change("CONDUITS", "P2", action="add", inlet_node="N2", outlet_node="missing",
             length=10, roughness=0.013, inlet_offset=0, outlet_offset=0)], "missing endpoint"),
    ([change("CONDUITS", "P2", action="add", inlet_node="N2", outlet_node="O1",
             length=10, roughness=0.013, inlet_offset=0, outlet_offset=0)], "missing cross section"),
    ([change("CONDUITS", "P2", action="add", inlet_node="N2", outlet_node="n2",
             length=10, roughness=0.013, inlet_offset=0, outlet_offset=0)], "endpoints must differ"),
    ([change("XSECTIONS", "missing", action="add", shape="CIRCULAR", geom1=1,
             geom2=0, geom3=0, geom4=0)], "missing link"),
    ([change("COORDINATES", "missing", action="add", x=0, y=0)], "missing node"),
])
def test_batch_dependency_checks(changes: list[Change], message: str) -> None:
    """New records need all hydraulic references, even when instructions are valid."""
    with pytest.raises(ValueError, match=message):
        apply_changes(document(), changes)


@pytest.mark.parametrize("item,stub", [
    (change(inlet_node="N2"), "STUB_REWIRE_CONVERSION"),
    (change(outlet_node="O1"), "STUB_REWIRE_CONVERSION"),
    (change("XSECTIONS", shape="RECT_CLOSED"), "STUB_REWIRE_CONVERSION"),
    (change("PUMPS", "P3", roughness=1), "STUB_SECTION_EDITING"),
    (change(action="delete", length=1), "STUB_DELETE_RENAME"),
])
def test_deferred_operations_fail_with_documented_stub(item: Change, stub: str) -> None:
    """Unsupported behavior cannot silently appear to succeed."""
    with pytest.raises(NotImplementedError, match=stub):
        apply_changes(document(), [item])


def test_force_main_roughness_and_unsupported_existing_shape() -> None:
    """Force-main coefficients differ from circular Manning roughness."""
    data = BASELINE.replace(b"P1 CIRCULAR 1 0 0 0", b"P1 FORCE_MAIN 1 100 0 0")
    result = apply_changes(document(data), [change("XSECTIONS", geom2=110)])
    assert b"P1 FORCE_MAIN 1 110 0 0" in result.data
    with pytest.raises(ValueError, match="force-main roughness"):
        apply_changes(document(data), [change("XSECTIONS", geom2=0)])
    data = BASELINE.replace(b"P1 CIRCULAR", b"P1 RECT_CLOSED")
    with pytest.raises(NotImplementedError, match="STUB_XSECTION_SHAPES"):
        apply_changes(document(data), [change("XSECTIONS", geom1=2)])


@pytest.mark.parametrize("section", ["CONDUITS", "XSECTIONS"])
@pytest.mark.parametrize("option,match", [
    (b"FLOW_ROUTING KINWAVE", "requires FLOW_ROUTING DYNWAVE"),
    (b"FORCE_MAIN_EQUATION MANNING", "FORCE_MAIN_EQUATION must be H-W or D-W"),
])
def test_touched_force_main_requires_supported_pressure_options(
    section: str, option: bytes, match: str,
) -> None:
    """Pressure context is checked for either link or cross-section edits."""
    data = BASELINE.replace(b"P1 CIRCULAR 1 0 0 0", b"P1 FORCE_MAIN 1 120 0 0")
    data = data.replace(b"FLOW_UNITS CFS", b"FLOW_UNITS CFS\r\n" + option)
    values = {"length": 125} if section == "CONDUITS" else {"geom1": 1.5}
    with pytest.raises(ValueError, match=match):
        apply_changes(document(data), [change(section, **values)])


def test_untouched_force_main_does_not_block_unrelated_junction_edit() -> None:
    """Inherited pressure options remain subject to separate engine review."""
    data = BASELINE.replace(b"P1 CIRCULAR 1 0 0 0", b"P1 FORCE_MAIN 1 120 0 0")
    data = data.replace(b"FLOW_UNITS CFS", b"FLOW_UNITS CFS\r\nFLOW_ROUTING KINWAVE")
    result = apply_changes(document(data), [change("JUNCTIONS", "N1", surcharge_depth=999)])
    assert b"N1 10 5 0 999" in result.data
    assert b"FLOW_ROUTING KINWAVE" in result.data


def test_hash_precondition_and_preview_apply_are_deterministic() -> None:
    """Preview bytes/audit are the exact candidate subsequently applied."""
    baseline = document()
    batch = [change(length=120, expected={"length": 100}), *addition_batch()]
    digest = sha256(BASELINE).hexdigest()
    preview = preview_changes(baseline, batch, expected_hash=digest)
    applied = apply_changes(baseline, batch, expected_hash=digest)
    assert applied == preview == preview_changes(baseline, batch, expected_hash=digest)
    assert preview.audit["baseline_sha256"] == digest
    assert preview.audit["candidate_sha256"] == sha256(preview.data).hexdigest()
    assert baseline.data == BASELINE
    with pytest.raises(ValueError, match="Stale baseline"):
        preview_changes(baseline, [], expected_hash="0" * 64)


def test_publication_preserves_source_and_writes_matching_readback_audit(tmp_path: Path) -> None:
    """Candidate and audit can be independently checked without touching baseline."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    result = edit_model(source, [change(length=120)], output, audit)
    assert source.read_bytes() == BASELINE
    assert read_document(output).data == result.data
    assert json.loads(audit.read_text(encoding="utf-8")) == result.audit
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit.json", "candidate.inp", "source.inp"]


@pytest.mark.parametrize("collision", ["source-output", "output-audit", "existing-output", "existing-audit"])
def test_publication_rejects_path_collisions_without_modifying_any_file(tmp_path: Path, collision: str) -> None:
    """Existing user files and the source can never be overwritten."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    if collision == "source-output":
        output = source
    elif collision == "output-audit":
        audit = output
    elif collision == "existing-output":
        output.write_bytes(b"existing candidate")
    else:
        audit.write_bytes(b"existing audit")
    before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    with pytest.raises((ValueError, FileExistsError)):
        edit_model(source, [change(length=120)], output, audit)
    assert {path: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_failed_staged_readback_cleans_temporary_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation failure before publication leaves only the untouched source."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    original_reader = editing.read_document

    def mismatched_reader(path: str | Path, encoding: str = "utf-8") -> SWMMDocument:
        """Simulate a file reader detecting corrupt staging content."""
        if Path(path).suffix == ".tmp":
            return document(b"[OPTIONS]\nFLOW_UNITS CFS\n")
        return original_reader(path, encoding=encoding)

    monkeypatch.setattr(editing, "read_document", mismatched_reader)
    with pytest.raises(ValueError, match="readback mismatch"):
        edit_model(source, [change(length=120)], output, audit)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == BASELINE


def test_audit_publication_collision_retains_concurrent_file_and_removes_owned_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Late audit collision removes our candidate while preserving the winner."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    original_publish = editing._publish_file

    def competing_publish(stage: Path, destination: Path) -> None:
        """Simulate another user atomically publishing an audit first."""
        if Path(destination) == audit:
            audit.write_bytes(b"concurrent user audit")
        original_publish(stage, destination)

    monkeypatch.setattr(editing, "_publish_file", competing_publish)
    with pytest.raises(FileExistsError):
        edit_model(source, [change(length=120)], output, audit)
    assert not output.exists()
    assert audit.read_bytes() == b"concurrent user audit"
    assert source.read_bytes() == BASELINE
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit.json", "source.inp"]


def test_add_complete_network_into_absent_supported_sections() -> None:
    """Sections absent from a small source can be added with complete dependencies."""
    data = b"[OPTIONS]\nFLOW_UNITS CFS\n[OUTFALLS]\nO1 0 FREE NO"
    instructions = [
        change("JUNCTIONS", "N1", action="add", invert_elevation=5, max_depth=3),
        change("CONDUITS", "P1", action="add", inlet_node="N1", outlet_node="O1",
               length=20, roughness=0.013, inlet_offset=0, outlet_offset=0),
        change("XSECTIONS", "P1", action="add", shape="CIRCULAR", geom1=1,
               geom2=0, geom3=0, geom4=0),
        change("COORDINATES", "N1", action="add", x=0, y=10),
    ]
    candidate = document(apply_changes(document(data), instructions).data)
    assert set(candidate.sections) == {"OPTIONS", "OUTFALLS", "JUNCTIONS", "CONDUITS", "XSECTIONS", "COORDINATES"}
    assert candidate.records("CONDUITS")[0].tokens == ("P1", "N1", "O1", "20", "0.013", "0", "0")


def test_unknown_record_tails_are_not_deleted_by_supported_field_edit() -> None:
    """A supported edit must retain vendor columns beyond the known EPA fields."""
    data = BASELINE.replace(b"P1 CIRCULAR 1 0 0 0", b"P1 CIRCULAR 1 0 0 0 1 0 VENDOR_TAIL")
    result = apply_changes(document(data), [change("XSECTIONS", geom1=2)])
    assert result.data == data.replace(b"P1 CIRCULAR 1 0", b"P1 CIRCULAR 2 0")


def test_source_changed_before_publication_rejects_without_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External source changes invalidate the candidate's publication precondition."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    original_reader = editing.read_document

    def concurrent_source_change(path: str | Path, encoding: str = "utf-8") -> SWMMDocument:
        """Simulate an external process replacing the baseline during staging."""
        result = original_reader(path, encoding=encoding)
        if Path(path).suffix == ".tmp":
            source.write_bytes(BASELINE + b"\n; external modification")
        return result

    monkeypatch.setattr(editing, "read_document", concurrent_source_change)
    with pytest.raises(ValueError, match="Source changed"):
        edit_model(source, [change(length=120)], output, audit)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == BASELINE + b"\n; external modification"


def test_staging_flush_failure_removes_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An I/O failure cannot leave a staged file that resembles a finished output."""
    source, output, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)

    def failing_flush(descriptor: int) -> None:
        """Simulate a storage synchronization failure."""
        raise OSError("simulated flush failure")

    monkeypatch.setattr(editing.os, "fsync", failing_flush)
    with pytest.raises(OSError, match="flush failure"):
        edit_model(source, [change(length=120)], output, audit)
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == BASELINE


def test_missing_output_parent_rejects_before_any_publication(tmp_path: Path) -> None:
    """Missing output directories require explicit caller preparation."""
    source = tmp_path / "source.inp"
    source.write_bytes(BASELINE)
    with pytest.raises(FileNotFoundError):
        edit_model(source, [change(length=120)], tmp_path / "missing" / "candidate.inp", tmp_path / "audit.json")
    assert list(tmp_path.iterdir()) == [source]


def test_cross_section_edit_cannot_target_a_pump() -> None:
    """Pump links do not have conduit cross-section contracts."""
    data = BASELINE.replace(b"[XSECTIONS]", b"[PUMPS]\r\nP2 N2 O1 C1\r\n[XSECTIONS]")
    item = change("XSECTIONS", "P2", action="add", shape="CIRCULAR", geom1=1,
                  geom2=0, geom3=0, geom4=0)
    with pytest.raises(NotImplementedError, match="STUB_XSECTION_LINK_TYPES"):
        apply_changes(document(data), [item])


def test_opaque_hydraulic_section_blocks_edit_but_allows_exact_no_op() -> None:
    """Unknown hydraulic dependencies require explicit implementation before edits."""
    data = BASELINE.replace(b"[BACKDROP]", b"[UNKNOWN_HYDRAULIC_CARD]\nP1 dependency\n[BACKDROP]")
    original = document(data)
    assert apply_changes(original, []).data == data
    with pytest.raises(NotImplementedError, match="STUB_|unsupported|uninterpreted"):
        apply_changes(original, [change(length=120)])
