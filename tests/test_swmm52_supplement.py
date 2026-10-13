"""Verify lexical retention of newer and deferred SWMM syntax.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Manually maintained. Fixture does not establish solver acceptance.
"""

from pathlib import Path

from hymo.document import SWMMDocument


FIXTURE = Path(__file__).parent / "fixtures" / "swmm52_supplement.inp"


def test_newer_and_deferred_syntax_is_available_without_truncation() -> None:
    """Retain repeated records, expressions, quoted paths, and unknown cards."""
    source_bytes = FIXTURE.read_bytes()
    document = SWMMDocument.from_bytes(source_bytes)

    assert document.data == source_bytes
    assert "".join(document.lines).encode(document.encoding) == source_bytes
    assert document.sections["JUNCTIONS"].records[0].tokens[0] == "001"
    assert document.sections["CONDUITS"].records[0].tokens[5] == "*"
    assert document.sections["XSECTIONS"].records[1].tokens == (
        "ROAD1", "STREET", "ROAD_SECTION"
    )
    assert [record.tokens[0] for record in document.sections["INLETS"].records] == [
        "COMBO1", "COMBO1", "CUSTOM1"
    ]
    assert document.sections["STORAGE"].records[0].tokens[4] == "CYLINDRICAL"
    assert document.sections["CURVES"].records[0].tokens[1] == "PUMP5"
    assert document.sections["TIMESERIES"].records[0].tokens[2] == (
        "resources/synthetic rain.dat"
    )
    assert len(document.sections["LID_CONTROLS"].records) == 4
    assert document.sections["VENDOR_EXTENSION"].records[0].tokens == (
        "INVENTED_KEY", "opaque value", "0007"
    )
    assert "EXPRESSION DepthMargin = WellDepth - 0.5" in document.text
    assert "SYNTHETIC_CATCHMENT LATERAL 0.001 * (Hgw - Hsw)" in document.text


def test_supplement_retains_all_original_text_with_explicit_windows_encoding() -> None:
    """Retain source positions and mixed newline styles without normalizing."""
    fixture_text = FIXTURE.read_bytes().decode("utf-8")
    mixed_source = fixture_text.replace("\r\n", "\n").replace(
        "[CONTROLS]\n", "[CONTROLS]\r\n"
    )
    source_bytes = mixed_source.encode("cp1252")
    document = SWMMDocument.from_bytes(source_bytes, encoding="cp1252")

    assert "".join(document.lines).encode("cp1252") == source_bytes
    for section in document.sections.values():
        for record in section.records:
            line = document.lines[record.line_index]
            for token, (start, end) in zip(record.tokens, record.spans, strict=True):
                assert line[start:end].strip('"') == token
