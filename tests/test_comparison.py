"""Verify manual QA diffs against requested and unexpected model effects.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-14
Notes: Synthetic, manually maintained regression and preservation tests.
"""

from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path

import pytest

from hymo import SWMMDocument, read_document
from shmm import (Change, VertexChange, compare_written_model, edit_model,
                  preview_model_diff, write_diff_reports)


BASELINE = (b'; retained note\r\n[OPTIONS]\r\nFLOW_UNITS CFS\r\nLINK_OFFSETS DEPTH\r\n'
            b'[JUNCTIONS]\r\nN1 10 5\r\nN2 8 6\r\n'
            b'[CONDUITS]\r\nP1 N1 N2 100 0.013 0 0 ; retained\r\n'
            b'[XSECTIONS]\r\nP1 CIRCULAR 1 0 0 0\r\n'
            b'[COORDINATES]\r\nN1 0 0\r\nN2 100 0\r\n'
            b'[DWF]\r\nN1 FLOW 0.2\r\nN1 TSS 5\r\n'
            b'[CURVES]\r\nC1 PUMP1 0 0\r\nC1 1 2\r\n'
            b'[CONTROLS]\r\nRULE X\r\nIF NODE N1 DEPTH > 1\r\nTHEN PUMP PP STATUS = OFF\r\n')


def document(data: bytes = BASELINE) -> SWMMDocument:
    """Build a lossless synthetic source document."""
    return SWMMDocument.from_bytes(data)


def instruction(value: object = 0.02, *, source_key: str = 'roughness-1') -> Change:
    """Build one finished, explicitly requested field update."""
    return Change('update', 'CONDUITS', 'P1', {'roughness': value}, source_key)


def test_preview_effects_evidence_and_noop() -> None:
    """Evidence and no-op requests survive independently of actual field effects."""
    evidence = {'roughness-1': {'basis': 'material policy', 'qa_flags': ['provisional'], 'units': 'Manning n'}}
    diff = preview_model_diff(document(), [instruction(), Change('update', 'JUNCTIONS', 'N1', {'max_depth': 5}, 'noop')], evidence=evidence)
    report = diff.report
    assert report['baseline_sha256'] == sha256(BASELINE).hexdigest()
    assert report['candidate_sha256'] == sha256(diff.candidate_data).hexdigest()
    assert report['verification'] == {'matches_expected': True, 'exact_bytes_checked': True, 'unexpected_effects': 0, 'missing_effects': 0, 'requested_noops': 1}
    assert len(report['effects']) == 1
    row = report['effects'][0]
    assert (row['field'], row['before'], row['after']) == ('roughness', '0.013', '0.02')
    assert row['source_keys'] == ['roughness-1']
    assert row['evidence'] == [evidence['roughness-1']]
    assert report['requested_operations'][1]['changed'] is False
    evidence['roughness-1']['qa_flags'].append('mutated')
    assert row['evidence'][0]['qa_flags'] == ['provisional']


def test_written_file_readback_matches_preview(tmp_path: Path) -> None:
    """The written check reads a published model, independently replaying requests."""
    source = tmp_path / 'source.inp'
    source.write_bytes(BASELINE)
    target = tmp_path / 'candidate.inp'
    changes = [instruction()]
    preview = preview_model_diff(read_document(source), changes)
    edit_model(source, changes, target, tmp_path / 'audit.json')
    written = compare_written_model(read_document(source), read_document(target), changes)
    assert written.report['stage'] == 'written_model'
    assert written.report['verification']['matches_expected']
    assert written.report['effects'] == preview.report['effects']
    assert source.read_bytes() == BASELINE


@pytest.mark.parametrize('old,new', [
    (b'N2 8 6', b'N2 9 6'),
    (b'; retained note', b'; changed note'),
    (b'N1 TSS 5', b'N1 TSS 8'),
    (b'C1 1 2', b'C1 1 3'),
    (b'IF NODE N1 DEPTH > 1', b'IF NODE N1 DEPTH > 3'),
    (b'P1 N1 N2', b'P1  N1 N2'),
    (b'[DWF]', b'[DWF] ; header changed'),
    (b'\r\n', b'\n'),
])
def test_unrequested_changes_cannot_pass(old: bytes, new: bytes) -> None:
    """Exact expected-byte reconciliation detects semantic and lexical mutations."""
    preview = preview_model_diff(document(), [instruction()])
    altered = document(preview.candidate_data.replace(old, new))
    written = compare_written_model(document(), altered, [instruction()])
    assert written.report['verification']['matches_expected'] is False
    assert written.report['unexpected_text_diff']
    assert written.report['candidate_sha256'] != written.report['expected_candidate_sha256']


def test_missing_and_wrong_requested_values() -> None:
    """A withheld instruction and a wrong value are both explicit QA failures."""
    missing = compare_written_model(document(), document(), [instruction()])
    assert missing.report['verification']['missing_effects'] == 1
    assert missing.report['missing_expected_effects'][0]['field'] == 'roughness'
    wrong = compare_written_model(document(), document(BASELINE.replace(b'0.013', b'0.03')), [instruction()])
    assert wrong.report['verification']['unexpected_effects'] == 1
    assert wrong.report['effects'][0]['reconciliation'] == 'unexpected_effect'


def test_repeated_lexical_ids_not_collapsed() -> None:
    """Changing one curve/DWF occurrence leaves its siblings visible and intact."""
    updated = document(BASELINE.replace(b'N1 TSS 5', b'N1 TSS 7').replace(b'C1 1 2', b'C1 1 4'))
    result = compare_written_model(document(), updated, [])
    rows = result.report['effects']
    assert len(rows) == 4
    assert [row['before'] or row['after'] for row in rows] == [['N1', 'TSS', '5'], ['N1', 'TSS', '7'], ['C1', '1', '2'], ['C1', '1', '4']]
    assert all(row['reconciliation'] == 'unexpected_effect' for row in rows)
    assert 'lexical' in result.report['section_matching']['CURVES']


def test_vertex_order_duplicates_and_empty_request() -> None:
    """Repeated XY rows remain ordered; straight-link requests remain audited."""
    changes = [VertexChange('P1', [(20, 1), (20, 1), (80, 3)], 'bends')]
    result = preview_model_diff(document(), [], vertex_changes=changes)
    row = result.report['effects'][0]
    assert row['after'] == [['20', '1'], ['20', '1'], ['80', '3']]
    reordered = result.candidate_data.replace(b'P1 20 1\r\nP1 20 1\r\nP1 80 3', b'P1 80 3\r\nP1 20 1\r\nP1 20 1')
    wrong = compare_written_model(document(), document(reordered), [], vertex_changes=changes)
    assert wrong.report['verification']['matches_expected'] is False
    assert wrong.report['effects'][0]['reconciliation'] == 'unexpected_effect'
    straight = preview_model_diff(document(), [], vertex_changes=[VertexChange('P1', [], 'straight')])
    assert straight.report['verification']['requested_noops'] == 1
    assert straight.report['effects'] == []


def test_added_fields_units_and_baseline_only_assets() -> None:
    """New defaults are effects, but baseline-only assets never imply deletion."""
    result = preview_model_diff(document(), [Change('add', 'JUNCTIONS', 'N3', {'invert_elevation': 7, 'max_depth': 4}, 'new-node')])
    assert len(result.report['effects']) == 5
    assert all(row['object_id'] == 'N3' and row['action'] == 'add' for row in result.report['effects'])
    assert result.report['effects'][0]['units'] == 'ft'
    assert all(row['reconciliation'] == 'requested_effect' for row in result.report['effects'])


def test_opaque_tail_and_vendor_cards_are_compared() -> None:
    """Unsupported tails/cards remain lexical and never acquire invented fields."""
    original = document(BASELINE + b'[VENDOR]\r\nA X\r\nA Y\r\n')
    candidate = document((BASELINE + b'[VENDOR]\r\nA X\r\nA Z\r\n').replace(b'N1 10 5', b'N1 10 5 0 0 0 EXTRA'))
    result = compare_written_model(original, candidate, [])
    assert any(row['field'] == 'opaque_tail' for row in result.report['effects'])
    assert len([row for row in result.report['effects'] if row['section'] == 'VENDOR']) == 2
    assert not result.report['verification']['matches_expected']


def test_duplicate_supported_ids_and_malformed_rows_use_lexical_fallback() -> None:
    """An independent written diff can diagnose ambiguous candidate grammar."""
    for suffix in (b'N1 10 5\r\n', b'BAD\r\n'):
        modified = BASELINE.replace(b'N2 8 6\r\n', b'N2 8 6\r\n' + suffix)
        result = compare_written_model(document(), document(modified), [])
        assert 'lexical' in result.report['section_matching']['JUNCTIONS']
        assert not result.report['verification']['matches_expected']


def test_reports_escaped_searchable_and_nonoverwriting(tmp_path: Path) -> None:
    """Untrusted evidence cannot inject markup/scripts or spreadsheet formulas."""
    evidence = {'=external-key': {'basis': '<script>alert(1)</script>', 'qa_flags': ['direction mismatch'], 'units': 'ft'}}
    result = preview_model_diff(document(), [instruction(source_key='=external-key')], evidence=evidence)
    paths = write_diff_reports(result, tmp_path, prefix='preview_diff')
    assert json.loads(paths['json'].read_text(encoding='utf-8')) == result.report
    markup = paths['html'].read_text(encoding='utf-8')
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in markup
    assert '<script>alert(1)</script>' not in markup
    assert 'direction mismatch' in markup and 'addEventListener' in markup
    with paths['csv'].open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2 and 'direction mismatch' in rows[0]['evidence']
    prior = {name: path.read_bytes() for name, path in paths.items()}
    with pytest.raises(FileExistsError):
        write_diff_reports(result, tmp_path, prefix='preview_diff')
    assert prior == {name: path.read_bytes() for name, path in paths.items()}


@pytest.mark.parametrize('prefix', ['', '../bad', 'a/b', 'a\\b', '.', '..', 'C:bad'])
def test_report_prefix_cannot_escape_directory(tmp_path: Path, prefix: str) -> None:
    """Reject path-containing report stems before creating anything."""
    with pytest.raises(ValueError):
        write_diff_reports(preview_model_diff(document(), []), tmp_path, prefix=prefix)
    assert list(tmp_path.iterdir()) == []


def test_stale_precondition_and_nonjson_evidence_rejected() -> None:
    """Diff inputs use the same baseline guard and a portable metadata contract."""
    with pytest.raises(ValueError, match='Stale baseline'):
        preview_model_diff(document(), [], expected_hash='wrong')
    with pytest.raises(ValueError):
        preview_model_diff(document(), [], evidence={'bad': float('nan')})


def test_noop_numeric_spelling_preserves_source_bytes() -> None:
    """Equivalent numeric spelling is a no-op and preserves the original text."""
    result = preview_model_diff(document(), [instruction('0.0130')])
    assert result.report['effects'] == []
    assert result.report['verification']['requested_noops'] == 1
    assert result.report['raw_text_diff'] == ''
    assert result.candidate_data == BASELINE


def test_csv_formula_text_is_protected(tmp_path: Path) -> None:
    """A formula-looking ID is rendered as text without mutating JSON values."""
    result = preview_model_diff(document(), [Change('add', 'JUNCTIONS', '=N3', {'invert_elevation': -1}, 'new')])
    paths = write_diff_reports(result, tmp_path)
    with paths['csv'].open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]['object_id'] == "'=N3"
    assert result.report['effects'][0]['object_id'] == '=N3'
