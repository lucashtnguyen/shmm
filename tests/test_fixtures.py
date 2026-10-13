"""Verify coordinated prepared fixtures and realistic editing acceptance cases.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained. Only prepared test inputs are used; preparation
tools, original identities and private source crosswalks are outside this repo.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
from typing import Any

import pytest

from hymo.document import SWMMDocument, read_document
from shmm.editing import Change, apply_changes, preview_changes

FIXTURES = Path(__file__).parent / "fixtures" / "network"
IDENTITY_FIELDS = {
    "update_id", "asset_id", "gis_id", "model_id", "structure_id", "from_node", "to_node",
    "walk_from", "walk_to", "model_ids", "gis_ids", "gis_key", "model_key", "model_keys",
    "gis_keys", "identity", "identity_members", "match_id", "issue_id", "source_issue_ids",
    "elevation_id", "related_run_ids", "predecessor_ids", "station_id", "station_key",
    "linked_structure_id", "discharge_pipe_ids", "review_pipe_ids", "receiving_node_ids",
    "model_pump_ids",
}
SCRUBBED_FIELDS = {
    "description", "reviewer", "review_notes", "station_names", "station_name", "inventory_name",
    "notes", "source_notes", "gis_notes", "model_notes", "evidence_hash", "analysis_evidence_hash",
    "run_signature", "gis_evidence", "recommendation", "evidence", "resolution_notes",
}


def _json(name: str) -> Any:
    """Read a prepared JSON artifact relative to the test fixture."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def portable_gis() -> dict[str, Any]:
    """Load the complete portable GIS fixture without an ArcGIS dependency."""
    return json.loads(gzip.decompress((FIXTURES / "updates.json.gz").read_bytes()))


def _records(document: SWMMDocument, section: str) -> dict[str, tuple[str, ...]]:
    """Index single-ID sections used in independently checked expectations."""
    return {record.tokens[0]: record.tokens for record in document.records(section)}


def test_complete_fixture_counts_and_map_identity(portable_gis: dict[str, Any]) -> None:
    """Check full dataset coverage and shared geometry against prepared INP."""
    manifest = _json("manifest.json")
    assert {name: len(data["records"]) for name, data in portable_gis.items()} == manifest["dataset_counts"]
    document = read_document(FIXTURES / "baseline.inp")
    assert len(document.records("CONDUITS")) == 263
    assert len(document.records("JUNCTIONS")) == 263
    assert len(document.records("PUMPS")) == 4
    assert len(document.records("STORAGE")) == 3
    assert len(document.records("WEIRS")) == 1
    assert set(document.sections) == set(manifest["section_counts"])
    coordinates = {r.tokens[0]: tuple(map(float, r.tokens[1:3])) for r in document.records("COORDINATES")}
    for pipe in portable_gis["Model_Update_Pipes"]["records"]:
        paths = pipe["geometry"]["paths"]
        for field, endpoint in (("from_node", paths[0][0]), ("to_node", paths[-1][-1])):
            if pipe[field] in coordinates:
                assert tuple(endpoint) == coordinates[pipe[field]]
    assert not manifest["private_crosswalk_distributed"]


def test_neutral_identity_fields_and_synthetic_geometry(portable_gis: dict[str, Any]) -> None:
    """Guard against IDs, prose, geographic CRS, M/Z and original coordinate data."""
    identity_pattern = re.compile(r"(?:KEY:)?O\d{6}(?:; (?:KEY:)?O\d{6})*")
    for dataset in portable_gis.values():
        for record in dataset["records"]:
            for field in IDENTITY_FIELDS & record.keys():
                if record[field]:
                    assert identity_pattern.fullmatch(record[field]), (field, record[field])
            for field in SCRUBBED_FIELDS & record.keys():
                assert not record[field]
            geometry = record.get("geometry")
            if geometry:
                assert "spatialReference" not in geometry
                assert "hasZ" not in geometry and "hasM" not in geometry
                points = [point for path in geometry.get("paths", []) for point in path]
                if "x" in geometry:
                    points.append([geometry["x"], geometry["y"]])
                for point in points:
                    assert len(point) == 2
                    assert 0 <= point[0] <= 5000 and 0 <= point[1] <= 15000
            for field in ("x", "y"):
                if record.get(field) is not None:
                    assert 0 <= record[field] <= 15000
            if "geom_length_ft" in record:
                assert record["geom_length_ft"] is None
    document = read_document(FIXTURES / "baseline.inp")
    for section in ("JUNCTIONS", "OUTFALLS", "STORAGE", "CONDUITS", "PUMPS", "WEIRS", "COORDINATES", "VERTICES", "RDII", "RAINGAGES", "CURVES", "TIMESERIES", "PATTERNS", "HYDROGRAPHS", "DWF", "INFLOWS"):
        assert all(re.fullmatch(r"O\d{6}", r.tokens[0]) for r in document.records(section))
    assert not document.records("TAGS")
    assert all("FILE" not in r.tokens for r in document.records("TIMESERIES"))


def test_scoped_workload_and_approved_partial_fields() -> None:
    """Keep outside candidates and engineering holds distinct from finished patches."""
    inventory = _json("workload.json")
    assert len(inventory["records"]) + len(inventory["outside_scope"]) == inventory["full_network_candidate_pipes"] == 553
    assert len(inventory["records"]) == inventory["south_candidate_pipes"] == 310
    assert all(row["applicable"] for row in inventory["records"])
    assert all(not row["applicable"] for row in inventory["outside_scope"])
    for scenario in ("existing", "future"):
        summary = inventory["scenarios"][scenario]
        assert summary["priority_counts"] == {"1": 239, "2": 70}
        assert summary["diameter_only_partial_candidates"] == 14
        assert summary["held_candidates"] == 309
        assert all(row["holds"] for row in inventory["records"] if row[scenario] == "Include")
    approved = [r for r in inventory["records"] if r["approved_fields"]]
    assert len(approved) == 14
    assert all(r["approved_fields"] == ["XSECTIONS.geom1"] for r in approved)


def test_rebuilt_geodatabase_verification_report() -> None:
    """Require successful complete private preparation QA without source details."""
    report = _json("gdb_verification.json")
    assert report["status"] == "passed" and report["error_count"] == 0
    assert report["gdb_readback_counts"] == _json("manifest.json")["dataset_counts"]
    assert report["identity_mapping_field_checks"] > 350_000
    assert report["readback_attribute_checks"] > 1_700_000
    assert report["synthetic_geometry_checks"] > 15_000
    assert report["max_geometry_delta_ft"] <= report["geometry_tolerance_ft"] == 0.001
    assert report["source_files_unchanged_during_verification"]


@pytest.mark.parametrize("scenario,added_pipe_count", [("existing", 1), ("future", 2)])
def test_prepared_acceptance_edits(scenario: str, added_pipe_count: int, portable_gis: dict[str, Any]) -> None:
    """Verify reviewed dimensions, synthetic additions, audits and untouched records."""
    original = (FIXTURES / "baseline.inp").read_bytes()
    baseline = SWMMDocument.from_bytes(original)
    changes = [Change(**item) for item in _json(f"{scenario}_changes.json")]
    preview = preview_changes(baseline, changes)
    applied = apply_changes(baseline, changes)
    assert preview == applied
    assert apply_changes(baseline, changes) == applied
    assert baseline.data == original == (FIXTURES / "baseline.inp").read_bytes()
    candidate = SWMMDocument.from_bytes(applied.data)
    xsections = _records(candidate, "XSECTIONS")
    baseline_xsections = _records(baseline, "XSECTIONS")
    pipes_by_id = {pipe["asset_id"]: pipe for pipe in portable_gis["Model_Update_Pipes"]["records"]}
    reviewed = _json("expected_reviewed_updates.json")
    for expected in reviewed:
        target = expected["object_id"]
        assert float(xsections[target][2]) == pytest.approx(expected["supplied_diameter_in"] / 12)
        assert float(xsections[target][2]) == pytest.approx(expected["expected_ft"])
        assert xsections[target][:2] == baseline_xsections[target][:2]
        assert xsections[target][3:] == baseline_xsections[target][3:]
        source = pipes_by_id[expected["source_key"]]
        assert source["model_ids"] == target
        assert source["gis_diameter_in"] == expected["supplied_diameter_in"]
        conduit = _records(baseline, "CONDUITS")[target]
        assert conduit[1:3] == (source["from_node"], source["to_node"])
    for expected in _json("expected_synthetic_additions.json"):
        if scenario not in expected["scenarios"]:
            assert expected["object_id"] not in _records(candidate, "CONDUITS")
            continue
        conduit = _records(candidate, "CONDUITS")[expected["object_id"]]
        junction = _records(candidate, "JUNCTIONS")[expected["new_node_id"]]
        assert conduit[1:3] == (expected["inlet_node"], expected["outlet_node"])
        assert float(conduit[3]) == expected["length_ft"] == 100
        assert float(conduit[4]) == expected["roughness"] == 0.013
        assert all(float(value) == 0 for value in conduit[5:])
        assert float(junction[1]) == expected["new_node_invert_ft"]
        assert float(junction[2]) == expected["new_node_max_depth_ft"] == 12
        assert float(xsections[expected["object_id"]][2]) == expected["diameter_ft"] == 1
        assert expected["new_node_id"] in _records(candidate, "COORDINATES")
    assert len(candidate.records("CONDUITS")) == 263 + added_pipe_count
    assert len(candidate.records("JUNCTIONS")) == 263 + added_pipe_count
    assert len(applied.audit["changes"]) == 14 + 4 * added_pipe_count
    assert all(row["source_key"].startswith("SYNTHETIC_") for row in applied.audit["changes"] if row["action"] == "add")
    touched = {(change.section, change.object_id) for change in changes}
    for section in ("CONDUITS", "JUNCTIONS", "XSECTIONS", "COORDINATES"):
        observed = _records(candidate, section)
        for key, tokens in _records(baseline, section).items():
            if (section, key) not in touched:
                assert observed[key] == tokens
    for section in set(baseline.sections) - {"CONDUITS", "JUNCTIONS", "XSECTIONS", "COORDINATES"}:
        before_section = baseline.sections[section]
        after_section = candidate.sections[section]
        assert baseline.lines[before_section.header_line:before_section.end_line] == candidate.lines[after_section.header_line:after_section.end_line]


def test_reviewed_patch_rejects_stale_baseline() -> None:
    """Regression: a changed baseline diameter must invalidate old-value evidence."""
    operations = _json("reviewed_existing_changes.json")
    operations[0]["expected"]["geom1"] += 1
    with pytest.raises(ValueError, match="stale"):
        apply_changes(read_document(FIXTURES / "baseline.inp"), [Change(**row) for row in operations])
