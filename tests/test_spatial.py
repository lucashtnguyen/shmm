"""Verify GIS export against independent shape readback and synthetic networks.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-15
Manually maintained synthetic cases. No private data or coordinates.
"""
from hashlib import sha256
import json
from pathlib import Path

import pytest

shapefile = pytest.importorskip("shapefile")
pytest.importorskip("pyproj")

from hymo import SWMMDocument
from shmm import GISAnnotation, GISFlag, export_shapefiles


MODEL = """[OPTIONS]
FLOW_UNITS CFS
[JUNCTIONS]
001 10 12.345
N2 8 6
X 10 4
Y 8 5
ALONE 0 1
[STORAGE]
S 0 5 0 FUNCTIONAL 1 0 1
[DIVIDERS]
D 0 P CUTOFF 1
[OUTFALLS]
O 0 FREE NO
O2 0 FREE NO
[CONDUITS]
P 001 N2 100 .013 0 0
Q X Y 25 .02 0 0
R S O2 10 .013 0 0
[PUMPS]
PU N2 S * ON 0 0
[WEIRS]
W S D TRANSVERSE 0 1 NO 0 0
[ORIFICES]
OR D O SIDE 0 .65 NO 0
[OUTLETS]
OU D O TABULAR/DEPTH * NO
[XSECTIONS]
P CIRCULAR 1 0 0 0
Q CIRCULAR 1 0 0 0
R CIRCULAR 1 0 0 0
[COORDINATES]
001 0 0
N2 100 0
S 110 0
D 120 0
O 130 0
O2 110 10
X 0 100
Y 25 100
[VERTICES]
p 20 5
P 60 2
"""


def document(text: str = MODEL) -> SWMMDocument:
    """Read an immutable synthetic model with metres-compatible map XY."""
    return SWMMDocument.from_bytes(text.encode("utf-8"))


def records(path: Path) -> dict[str, dict]:
    """Read DBF without going through SHMM's attribute preparation."""
    with shapefile.Reader(str(path), encoding="utf-8") as reader:
        return {row["MODEL_ID"]: row for row in (value.as_dict() for value in reader.records())}


def test_all_families_flags_components_and_geometry(tmp_path: Path) -> None:
    """Known baseline basins stay distinct from new islands and null geometry."""
    model = document()
    baseline = document("[JUNCTIONS]\n001 10 1\n[OUTFALLS]\nO2 0 FREE NO\n")
    annotations = [GISAnnotation("node", "001", [GISFlag("placeholder_rim", "placeholder", "max_depth", "reviewed sentinel")]),
                   GISAnnotation("link", "p", [GISFlag("assumed_n", "assumption", "roughness"), GISFlag("datum_screen", "provisional", "offset")])]
    result = export_shapefiles(model, tmp_path / "gis", crs="EPSG:3857", baseline=baseline,
                              annotations=annotations, annotation_model_sha256=sha256(model.data).hexdigest())
    assert result["counts"] == {"nodes": 9, "links": 7, "components": 3, "islands": 2, "null_geometries": 1}
    ns, ls = records(tmp_path / "gis/nodes"), records(tmp_path / "gis/links")
    assert ns["001"]["PLACEHOLDR"] == 1 and ns["001"]["MAX_DEPTH"] == 12.345
    assert ns["N2"]["PLACEHOLDR"] == -1 and ns["N2"]["QA_COVER"] == "unknown"
    assert ls["P"]["ASSUMED"] == 1 and ls["P"]["PROVISION"] == 1
    assert ls["P"]["XS_SHAPE"] == "CIRCULAR" and "SHAPE" not in ls["P"]
    assert ls["P"][result["flag_fields"]["assumed_n"]] == 1
    assert ls["Q"]["ISLAND_ID"] and ns["X"]["ISLAND_ID"] == ls["Q"]["ISLAND_ID"]
    assert ns["ALONE"]["GEOM_OK"] == 0 and ns["ALONE"]["IS_ISLAND"] == 1
    assert all(ls[key]["IS_ISLAND"] == 0 for key in ("P", "PU", "W", "OR", "OU", "R"))
    assert {row["SECTION"] for row in ls.values()} == {"CONDUITS", "PUMPS", "WEIRS", "ORIFICES", "OUTLETS"}
    with shapefile.Reader(str(tmp_path / "gis/links")) as reader:
        shapes = {entry.record.as_dict()["MODEL_ID"]: list(entry.shape.points) for entry in reader.iterShapeRecords()}
    assert shapes["P"] == [(0, 0), (20, 5), (60, 2), (100, 0)]
    assert shapes["PU"] == [(100, 0), (110, 0)]
    full = json.loads((tmp_path / "gis/qa_features.json").read_text(encoding="utf-8"))
    assert len(full) == 16 and next(row for row in full if row["object_id"] == "001")["flags"][0]["basis"] == "reviewed sentinel"
    assert model.data == MODEL.encode()


def test_no_annotation_or_baseline_does_not_claim_clean_or_island(tmp_path: Path) -> None:
    """A numerical sentinel and unanchored component alone establish no provenance."""
    result = export_shapefiles(document(), tmp_path / "gis", crs=3857)
    rows = records(tmp_path / "gis/nodes")
    assert rows["001"]["PLACEHOLDR"] == -1 and rows["001"]["ASSUMED"] == -1
    assert rows["X"]["IS_ISLAND"] == -1
    assert result["counts"]["islands"] == 0


def test_long_unicode_flags_preserved_and_stale_hash_rejected(tmp_path: Path) -> None:
    """Individual flag columns and JSON remain complete when the summary is short."""
    model = document()
    long_code = "flag_" + "é" * 150
    annotation = GISAnnotation("node", "001", [GISFlag(long_code, "assumption", evidence={"full": "retained"})])
    with pytest.raises(ValueError, match="hash"):
        export_shapefiles(model, tmp_path / "stale", crs=3857, annotations=[annotation], annotation_model_sha256="stale")
    result = export_shapefiles(model, tmp_path / "gis", crs=3857, annotations=[annotation], annotation_model_sha256=sha256(model.data).hexdigest())
    row = records(tmp_path / "gis/nodes")["001"]
    assert row["QA_TRUNC"] == 1 and row[result["flag_fields"][long_code]] == 1
    assert len(row["QA_FLAGS"].encode("utf-8")) <= 254
    full = json.loads((tmp_path / "gis/qa_features.json").read_text(encoding="utf-8"))
    assert next(row for row in full if row["object_id"] == "001")["flags"][0]["code"] == long_code


@pytest.mark.parametrize("text", [
    MODEL.replace("N2 8 6", "001 8 6"),
    MODEL.replace("P 001 N2", "P 001 MISSING"),
    MODEL.replace("N2 100 0", "N2 nan 0"),
    MODEL.replace("N2 100 0", "N2 1_00 0"),
    MODEL.replace("N2 100 0", "N2 100 0\nN2 100 0"),
    MODEL.replace("p 20 5", "MISSING 20 5"),
    MODEL.replace("Q X Y", "p X Y"),
])
def test_invalid_network_fails_before_output(tmp_path: Path, text: str) -> None:
    """Ambiguity and malformed geometry cannot publish incomplete bundles."""
    with pytest.raises(ValueError):
        export_shapefiles(document(text), tmp_path / "gis", crs=3857)
    assert not (tmp_path / "gis").exists()


def test_missing_and_degenerate_geometry_are_accounted_for(tmp_path: Path) -> None:
    """All assets remain in topology, with null shapes and explicit geometry QA."""
    model = document(MODEL.replace("Y 25 100", "Y 0 100").replace("N2 100 0\n", ""))
    result = export_shapefiles(model, tmp_path / "gis", crs=3857)
    rows = records(tmp_path / "gis/links")
    assert rows["P"]["GEOM_OK"] == 0 and rows["Q"]["GEOM_OK"] == 0
    assert result["counts"]["links"] == 7 and result["counts"]["null_geometries"] == 5


def test_components_are_deterministic_and_multiple_basins_supported(tmp_path: Path) -> None:
    """Baseline anchors preserve legitimate small basins, regardless of card order."""
    model = document()
    baseline = document("[JUNCTIONS]\n001 10 1\nX 10 1\n")
    first = export_shapefiles(model, tmp_path / "a", crs=3857, baseline=baseline)
    reordered = document(MODEL.replace("X 10 4\nY 8 5\n", "Y 8 5\nX 10 4\n"))
    second = export_shapefiles(reordered, tmp_path / "b", crs=3857, baseline=baseline)
    assert first["counts"]["islands"] == second["counts"]["islands"] == 1
    assert (tmp_path / "a/components.json").read_bytes() == (tmp_path / "b/components.json").read_bytes()
    assert records(tmp_path / "a/nodes")["X"]["IS_ISLAND"] == 0


def test_crs_annotation_validation_and_no_overwrite(tmp_path: Path) -> None:
    """Require explicit, two-dimensional CRS and exact evidence identities."""
    model = document()
    for crs in (None, "not-a-crs", 4979):
        with pytest.raises(ValueError):
            export_shapefiles(model, tmp_path / "bad", crs=crs)
    for annotations in ([GISAnnotation("node", "unknown")], [GISAnnotation("node", "001")] * 2,
                        [GISAnnotation("node", "001", [GISFlag("x", "invalid")])]):
        with pytest.raises(ValueError):
            export_shapefiles(model, tmp_path / "bad", crs=3857, annotations=annotations, annotation_model_sha256=sha256(model.data).hexdigest())
    target = tmp_path / "existing"
    target.mkdir()
    with pytest.raises(FileExistsError):
        export_shapefiles(model, target, crs=3857)


def test_write_failure_leaves_no_partial_bundle(tmp_path: Path, monkeypatch) -> None:
    """Staging failure preserves other directories and leaves target absent."""
    def fail(*args, **kwargs):
        raise OSError("injected writer failure")
    monkeypatch.setattr(shapefile.Writer, "point", fail)
    with pytest.raises(OSError):
        export_shapefiles(document(), tmp_path / "gis", crs=3857)
    assert list(tmp_path.iterdir()) == []


def test_separate_namespaces_geographic_crs_and_flag_names(tmp_path: Path) -> None:
    """Node/link IDs stay distinct and flag fields remain valid GIS identifiers."""
    model = document("[JUNCTIONS]\n001 1 1\n[OUTFALLS]\nO 0 FREE NO\n"
                     "[CONDUITS]\n001 001 O 10 .013 0 0\n"
                     "[COORDINATES]\n001 -120 45\nO -120.001 45\n")
    annotations = [GISAnnotation("node", "001", [GISFlag("123_numeric_flag", "qa")], coverage="complete"),
                   GISAnnotation("link", "001", coverage="partial")]
    result = export_shapefiles(model, tmp_path / "gis", crs=4326, annotations=annotations,
                              annotation_model_sha256=sha256(model.data).hexdigest())
    ns, ls = records(tmp_path / "gis/nodes"), records(tmp_path / "gis/links")
    assert ns["001"]["QA_KEY"] != ls["001"]["QA_KEY"]
    assert ns["001"]["QA_COVER"] == "complete"
    field = result["flag_fields"]["123_numeric_flag"]
    assert field[0].isalpha() and len(field) <= 10
    assert ns["001"][field] == 1 and ls["001"][field] == 0


def test_empty_network_retains_explicit_empty_layers(tmp_path: Path) -> None:
    """Empty input remains counted as empty rather than creating dummy geometry."""
    result = export_shapefiles(document("[OPTIONS]\nFLOW_UNITS CFS\n"), tmp_path / "gis", crs=3857)
    assert result["counts"] == {"nodes": 0, "links": 0, "components": 0, "islands": 0, "null_geometries": 0}
    assert records(tmp_path / "gis/nodes") == {}
    assert records(tmp_path / "gis/links") == {}


def test_transient_windows_lock_retries_without_partial_copy(tmp_path: Path, monkeypatch) -> None:
    """One brief sharing lock does not invalidate a completely verified bundle."""
    from shmm.spatial import _publish_directory

    stage, target = tmp_path / "stage", tmp_path / "gis"
    stage.mkdir()
    (stage / "complete").write_text("verified")
    original = Path.rename
    attempts = []

    def locked_once(self: Path, destination: Path) -> Path:
        attempts.append(self)
        if len(attempts) == 1:
            error = PermissionError("transient sharing lock")
            error.winerror = 32
            raise error
        return original(self, destination)

    monkeypatch.setattr(Path, "rename", locked_once)
    monkeypatch.setattr("shmm.spatial.time.sleep", lambda delay: None)
    _publish_directory(stage, target)
    assert len(attempts) == 2
    assert (target / "complete").read_text() == "verified"
