"""Check written-model loading validation and semantic fingerprints.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-11-13
Synthetic records only; no files are written.
"""

from hymo import SWMMDocument

from shmm import loading_fingerprint, validate_loading

BASE = """[OPTIONS]
FLOW_UNITS MGD
[JUNCTIONS]
A 1
B 1
[DWF]
A FLOW 0.1 H ; comment
[INFLOWS]
B FLOW TS FLOW 1.0 1.0 0.002
[RDII]
B UH 4
[PATTERNS]
H HOURLY 1 1 1 1 1 1 1 1 1 1 1 1
H 1 1 1 1 1 1 1 1 1 1 1 1
[TIMESERIES]
TS 0 1 24 1
"""


def test_valid_model_and_order_comment_insensitive_fingerprint() -> None:
    document = SWMMDocument.from_bytes(BASE.encode())
    report = validate_loading(document)
    assert report["passed"] and report["counts"]["DWF"] == 1 and report["flow_units"] == "MGD"
    reordered = BASE.replace("A FLOW 0.1 H ; comment", "a Flow 0.1 h")
    assert loading_fingerprint(SWMMDocument.from_bytes(reordered.encode())) == loading_fingerprint(document)
    changed = BASE.replace("0.002", "0.003")
    assert loading_fingerprint(SWMMDocument.from_bytes(changed.encode())) != loading_fingerprint(document)


def test_issues_and_warnings_are_explicit() -> None:
    text = (BASE.replace("[DWF]\n", "[DWF]\nZ FLOW 1\nA FLOW -1\n")
                .replace("B UH 4", "B UH -4")
                .replace("[TIMESERIES]\n", "[TIMESERIES]\nEXT FILE x.dat\n")
                .replace("FLOW_UNITS MGD\n", ""))
    report = validate_loading(SWMMDocument.from_bytes(text.encode()))
    assert not report["passed"]
    assert {"DWF:Z:undeclared_node", "DWF:A:FLOW:duplicate_row", "RDII:B:negative_area",
            "OPTIONS:FLOW_UNITS:missing"} <= set(report["issues"])
    assert {"DWF:A:negative_average", "TIMESERIES:EXT:external_file_not_read"} <= set(report["warnings"])


def test_rows_with_extra_trailing_tokens_are_read_and_only_warn() -> None:
    """SWMM applies a DWF row with empty slots after the fourth pattern; extra non-empty tokens warn."""
    text = BASE.replace("A FLOW 0.1 H ; comment", 'A FLOW 0.1 H "" "" "" ""').replace(
        "B FLOW TS FLOW 1.0 1.0 0.002", "B FLOW TS FLOW 1.0 1.0 0.002 \"\" EXTRA")
    report = validate_loading(SWMMDocument.from_bytes(text.encode()))
    assert report["passed"] and report["counts"]["DWF"] == 1 and report["counts"]["INFLOWS"] == 1
    assert report["record_counts"] == {"DWF": 1, "INFLOWS": 1, "RDII": 1}
    assert report["warnings"] == ["INFLOWS:B:ignored_extra_tokens"]


def test_duplicate_flow_rows_fail_in_both_sections() -> None:
    """The engine keeps only the last FLOW row per node and section, so duplicates fail."""
    text = BASE.replace("[DWF]\n", "[DWF]\nA Flow 0.2\n").replace("[INFLOWS]\n", "[INFLOWS]\nB FLOW \"\" FLOW 1 1 1\n")
    report = validate_loading(SWMMDocument.from_bytes(text.encode()))
    assert not report["passed"]
    assert {"DWF:A:FLOW:duplicate_row", "INFLOWS:B:FLOW:duplicate_row"} <= set(report["issues"])
