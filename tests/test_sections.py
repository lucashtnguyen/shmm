"""Exercise explicit finished-network publication and preservation boundaries.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-16
Notes: Synthetic models only; manually maintained regression tests.
"""

from hashlib import sha256
import json
from pathlib import Path

from hymo import SWMMDocument, read_document
import pytest

from shmm import (SectionPatch, compare_written_sections, preview_section_patches,
                  publish_section_patches)


BASELINE = (b'; original preamble\r\n[OPTIONS]\r\nFLOW_UNITS CFS\r\nLINK_OFFSETS DEPTH\r\n'
            b'FLOW_ROUTING DYNWAVE\r\nFORCE_MAIN_EQUATION H-W\r\n'
            b'[JUNCTIONS]\r\nN1 20 10\r\nN2 10 10\r\n'
            b'[OUTFALLS]\r\nEND 0 FREE NO\r\n'
            b'[PUMPS]\r\nPU N1 N2 PC OFF 5 2 ; old bypass\r\n'
            b'[CONDUITS]\r\nA N2 END 100 0.013 0 0\r\n'
            b'[XSECTIONS]\r\nA CIRCULAR 1 0 0 0\r\n'
            b'[CURVES]\r\n; preserve exact curve spelling\r\nPC PUMP3 0 1\r\nPC 10 0\r\n'
            b'[TIMESERIES]\r\nRAIN FILE "X:\\old rain.dat"\r\n'
            b'[RAINGAGES]\r\nRG INTENSITY 1:00 1 TIMESERIES RAIN\r\n'
            b'[INFLOWS]\r\nN1 FLOW RAIN FLOW 1 1 0\r\n'
            b'[CONTROLS]\r\nRULE SAFE\r\nIF NODE N1 DEPTH > 8\r\nTHEN PUMP PU STATUS = ON\r\n'
            b'[VENDOR]\r\nopaque untouched \xc3\xa9\r\n')


def document(data: bytes = BASELINE) -> SWMMDocument:
    """Read a synthetic lexical baseline."""
    return SWMMDocument.from_bytes(data)


def patch(section: str, *lines: str, **kwargs: object) -> SectionPatch:
    """Create a section request with traceable synthetic review basis."""
    return SectionPatch(section, lines, section.lower(), "Reviewed synthetic finished records", **kwargs)


def preview(patches: list[SectionPatch], **kwargs: object):
    """Apply requests with the exact synthetic source hash."""
    return preview_section_patches(document(), patches, baseline_sha256=sha256(BASELINE).hexdigest(), **kwargs)


def test_rewire_pump_to_force_main_start_and_replace_outfall() -> None:
    """A pump discharges to a new pressure node; old terminal becomes junction."""
    requests = [
        patch("JUNCTIONS", "N1 20 10", "N2 10 10", "DISCH 20 12.345 0 999 ; ASSUMED pressure elevation", "END 0 10"),
        patch("PUMPS", "PU N1 DISCH PC OFF 5 2 ; explicit force-main connection"),
        patch("CONDUITS", "A N2 END 100 0.013 0 0", "FM DISCH N2 300 0.013 0 0", "TAIL END FINAL 200 0.013 0 0"),
        patch("XSECTIONS", "A CIRCULAR 1 0 0 0", "FM FORCE_MAIN 1 120 0 0", "TAIL CIRCULAR 2 0 0 0"),
        patch("OUTFALLS", "FINAL -2 FREE NO ; PLACEHOLDER boundary"),
    ]
    result = preview(requests, require_connected=True, require_terminal_routes=True)
    topology = result.audit["topology"]
    assert topology["component_count"] == 1
    assert topology["nodes_without_terminal_route"] == []
    candidate = document(result.data)
    assert candidate.records("PUMPS")[0].tokens[2] == "DISCH"
    assert candidate.records("OUTFALLS")[0].tokens[0] == "FINAL"
    assert b"DISCH 20 12.345 0 999 ; ASSUMED" in result.data
    for name in ("CURVES", "VENDOR", "CONTROLS", "TIMESERIES", "RAINGAGES"):
        original_section = document().sections[name]
        actual_section = candidate.sections[name]
        assert document().lines[original_section.header_line:original_section.end_line] == candidate.lines[actual_section.header_line:actual_section.end_line]
    assert result.diff.report["verification"]["matches_expected"]
    assert BASELINE == document().data


def test_merge_removes_link_node_crosssection_and_geometry_together() -> None:
    """Explicit final records remove a short link and its retired references."""
    requests = [patch("JUNCTIONS", "N1 20 10"), patch("PUMPS", "PU N1 END PC OFF 5 2"),
                patch("CONDUITS"), patch("XSECTIONS"),
                patch("COORDINATES", "N1 0 0", "END 100 0"),
                patch("VERTICES", delete=True)]
    source = BASELINE + b"[VERTICES]\r\nA 1 2\r\n"
    result = preview_section_patches(document(source), requests, baseline_sha256=sha256(source).hexdigest(), require_connected=True, require_terminal_routes=True)
    candidate = document(result.data)
    assert len(candidate.records("JUNCTIONS")) == 1
    assert "VERTICES" not in candidate.sections
    assert not candidate.records("CONDUITS")
    assert not candidate.records("XSECTIONS")
    assert any(row["action"] == "remove" and row["object_id"] == "A" for row in result.diff.report["effects"])


def test_inline_forcing_preserves_duplicate_order_and_object_basis() -> None:
    """A FILE dependency is replaced by explicit constant rainfall observations."""
    evidence = {"RAIN": {"assumptions": ["constant_placeholder"], "units": "in/hr"}}
    request = patch("TIMESERIES", "RAIN 10/01/2020 00:00 0.012345 ; placeholder", "RAIN 10/01/2020 01:00 0.012345", object_evidence=evidence)
    result = preview([request])
    evidence["RAIN"]["assumptions"].append("later mutation")
    effect = next(row for row in result.diff.report["effects"] if row["section"] == "TIMESERIES")
    assert effect["evidence"][0]["object"]["assumptions"] == ["constant_placeholder"]
    assert b'FILE "X:' not in result.data
    assert len(document(result.data).records("TIMESERIES")) == 2
    assert "placeholder" in result.diff.report["raw_text_diff"]


@pytest.mark.parametrize("requests,match", [
    ([patch("JUNCTIONS", "N1 0 10", "n1 0 10")], "duplicate ID"),
    ([patch("JUNCTIONS", "N1 0 10", "N2 0 10", "end 0 10")], "Duplicate object ID"),
    ([patch("PUMPS", "PU N1 MISSING PC OFF 5 2")], "missing endpoint"),
    ([patch("PUMPS", "PU N1 N2 MISSING OFF 5 2")], "curve"),
    ([patch("JUNCTIONS", "N1 0 10")], "missing endpoint"),
    ([patch("CONDUITS")], "missing link"),
    ([patch("XSECTIONS")], "missing cross section"),
    ([patch("TIMESERIES")], "timeseries"),
    ([patch("CURVES")], "curve"),
    ([patch("JUNCTIONS", "N1 0 10", "N2 0 10", "LONE 0 10")], "one connected component"),
    ([patch("CONDUITS", "A END N2 100 .013 0 0")], "lack directed outfall routes"),
    ([patch("JUNCTIONS", "N1 NaN 10", "N2 0 10")], "finite SWMM number"),
    ([patch("PUMPS", "PU N1 N2 PC OFF 5 2\n[JUNCTIONS]")], "newline/control"),
    ([patch("PUMPS", "[JUNCTIONS]")], "header injection"),
    ([patch("COORDINATES", "N1 0 0", "n1 1 1")], "duplicate ID"),
    ([patch("XSECTIONS", "A CIRCULAR 1 0 0 0", "PU CIRCULAR 1 0 0 0")], "supported link type"),
    ([patch("LOSSES", "PU 0 0 0 NO")], "conduit"),
    ([patch("NEW", delete=True)], "existing section"),
    ([patch("PUMPS"), patch("pumps")], "Duplicate section patch"),
])
def test_reject_invalid_requests_and_final_topology(requests, match: str) -> None:
    """Invalid batches never produce a candidate or mutate their baseline."""
    with pytest.raises(ValueError, match=match):
        preview(requests, require_connected=True, require_terminal_routes=True)
    assert document().data == BASELINE


def test_stale_hash_and_unknown_section_preservation() -> None:
    """Stale preparation rejects; an untouched vendor section remains literal."""
    with pytest.raises(ValueError, match="SHA-256"):
        preview_section_patches(document(), [], baseline_sha256="0" * 64)
    result = preview([])
    assert result.data == BASELINE
    assert result.diff.report["verification"]["requested_noops"] == 0
    assert any(row["section"] == "VENDOR" for row in result.audit["preserved_sections"])


def test_untouched_controls_and_loads_cannot_reference_deleted_objects() -> None:
    """Deleting nodes or pumps requires explicit control and load reconciliation."""
    with pytest.raises(ValueError, match="CONTROLS"):
        preview([patch("PUMPS")])
    with pytest.raises(ValueError, match="missing node"):
        preview([patch("JUNCTIONS", "N2 10 10"), patch("PUMPS"), patch("CONTROLS")])


def test_written_comparison_detects_comment_and_opaque_mutation() -> None:
    """Readback reconciliation includes text outside named hydraulic fields."""
    requests = [patch("PUMPS", "PU N1 N2 PC OFF 5 2 ; basis approved")]
    result = preview(requests)
    changed = result.data.replace(b"basis approved", b"basis lost").replace(b"opaque untouched", b"opaque changed")
    diff = compare_written_sections(document(), document(changed), requests, baseline_sha256=sha256(BASELINE).hexdigest())
    assert not diff.report["verification"]["matches_expected"]
    assert diff.report["verification"]["unexpected_effects"] > 0
    assert "basis lost" in diff.report["unexpected_text_diff"]


def test_publish_new_candidate_and_both_diffs(tmp_path: Path) -> None:
    """Publication emits exact bytes and completion evidence only after readback."""
    source, target, audit = (tmp_path / name for name in ("source.inp", "candidate.inp", "audit.json"))
    source.write_bytes(BASELINE)
    result = publish_section_patches(source, target, [patch("TIMESERIES", "RAIN 10/01/2020 00:00 0")],
                                     baseline_sha256=sha256(BASELINE).hexdigest(), audit_path=audit,
                                     require_connected=True, require_terminal_routes=True)
    assert source.read_bytes() == BASELINE
    assert target.read_bytes() == result.data
    assert result.written_diff.report["verification"]["matches_expected"]
    assert json.loads(audit.read_text(encoding="utf-8"))["status"] == "published"
    for name in ("preview_diff", "written_model_diff"):
        for suffix in ("json", "csv", "html"):
            assert (tmp_path / f"{name}.{suffix}").is_file()
    assert read_document(target).data == result.data


def test_publication_path_collision_preserves_existing_files(tmp_path: Path) -> None:
    """No output, audit or report path may overwrite the source or another file."""
    source = tmp_path / "source.inp"
    source.write_bytes(BASELINE)
    with pytest.raises(ValueError, match="paths must differ"):
        publish_section_patches(source, source, [], baseline_sha256=sha256(BASELINE).hexdigest(), audit_path=tmp_path / "audit.json")
    reserved = tmp_path / "written_model_diff.csv"
    reserved.write_bytes(b"retain me")
    with pytest.raises(FileExistsError):
        publish_section_patches(source, tmp_path / "new.inp", [], baseline_sha256=sha256(BASELINE).hexdigest(), audit_path=tmp_path / "audit.json")
    assert reserved.read_bytes() == b"retain me"
    assert not (tmp_path / "new.inp").exists()


def test_caught_publication_failure_removes_only_owned_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An audit failure leaves no success-looking candidate or partial reports."""
    import shmm.sections as sections

    source = tmp_path / "source.inp"
    source.write_bytes(BASELINE)
    publish = sections._publish_file

    def fail_audit(stage: Path, target: Path) -> None:
        if target.name == "audit.json":
            raise OSError("injected audit publication failure")
        publish(stage, target)

    monkeypatch.setattr(sections, "_publish_file", fail_audit)
    with pytest.raises(OSError, match="injected"):
        publish_section_patches(source, tmp_path / "new.inp", [], baseline_sha256=sha256(BASELINE).hexdigest(), audit_path=tmp_path / "audit.json")
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes() == BASELINE


def test_append_refuses_unrequested_missing_eof_newline_change() -> None:
    """Adding a header never silently modifies a preceding untouched section."""
    source = BASELINE.rstrip(b"\r\n")
    with pytest.raises(ValueError, match="final newline"):
        preview_section_patches(document(source), [patch("MAP", "UNITS FEET")], baseline_sha256=sha256(source).hexdigest())


@pytest.mark.parametrize("clause", ["IF NODE N1 DEPTH > NODE GONE DEPTH",
                                  "THEN PUMP PU SETTING = CURVE GONE",
                                  "THEN PUMP PU SETTING = TIMESERIES GONE"])
def test_control_secondary_references_are_not_left_dangling(clause: str) -> None:
    """Object comparisons and modulated settings retain their dependencies."""
    with pytest.raises(ValueError, match="CONTROLS"):
        preview([patch("CONTROLS", "RULE EXPLICIT", clause)])


def test_repeated_forcing_rows_reconcile_each_occurrence() -> None:
    """An omitted repeated curve/time row produces a missing effect in readback."""
    requests = [patch("TIMESERIES", "RAIN 10/01/2020 00:00 0", "RAIN 10/01/2020 01:00 0", "RAIN 10/01/2020 01:00 0")]
    result = preview(requests)
    actual = result.data.replace(b"RAIN 10/01/2020 01:00 0\r\n", b"", 1)
    diff = compare_written_sections(document(), document(actual), requests, baseline_sha256=sha256(BASELINE).hexdigest())
    assert not diff.report["verification"]["matches_expected"]
    assert diff.report["verification"]["missing_effects"] == 1


def test_source_change_during_publication_cannot_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A concurrent baseline edit aborts publication and preserves that edit."""
    import shmm.sections as sections

    source = tmp_path / "source.inp"
    source.write_bytes(BASELINE)
    write_reports = sections.write_diff_reports

    def concurrent_edit(*args, **kwargs):
        paths = write_reports(*args, **kwargs)
        source.write_bytes(BASELINE + b"; concurrently reviewed\r\n")
        return paths

    monkeypatch.setattr(sections, "write_diff_reports", concurrent_edit)
    with pytest.raises(ValueError, match="Source changed"):
        publish_section_patches(source, tmp_path / "new.inp", [], baseline_sha256=sha256(BASELINE).hexdigest(), audit_path=tmp_path / "audit.json")
    assert list(tmp_path.iterdir()) == [source]
    assert source.read_bytes().endswith(b"; concurrently reviewed\r\n")


def test_noop_body_and_bom_preservation() -> None:
    """An explicit identical body is a no-op, including UTF-8 BOM and CRLF."""
    source = b"\xef\xbb\xbf" + BASELINE
    result = preview_section_patches(document(source), [patch("JUNCTIONS", "N1 20 10", "N2 10 10")], baseline_sha256=sha256(source).hexdigest())
    assert result.data == source
    assert result.diff.report["verification"]["requested_noops"] == 1


@pytest.mark.parametrize("kwargs", [{"basis": ""}, {"source_key": "\nBAD"}, {"delete": "yes"},
                                   {"lines": "N1 0 10"}, {"object_evidence": {"N1": float("nan")}},
                                   {"object_evidence": {"N1": {}, "n1": {}}}])
def test_invalid_instruction_metadata_is_rejected(kwargs) -> None:
    """Audits cannot accept absent basis, nonfinite JSON or ambiguous identities."""
    fields = {"section": "JUNCTIONS", "lines": ["N1 20 10", "N2 10 10"], "source_key": "reviewed", "basis": "source record"}
    fields.update(kwargs)
    with pytest.raises((ValueError, TypeError)):
        preview([SectionPatch(**fields)])
