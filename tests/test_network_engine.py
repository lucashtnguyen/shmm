"""Opt-in engine compatibility checks for the prepared network and two scenarios.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained. Synthetic zero rainfall limits interpretation to
engine compatibility; these checks do not prove hydraulic equivalence.
"""

import json
import os
from pathlib import Path

import pytest

from hymo import read_document
from shmm import Change, apply_changes
from shmm.engine import check_engine

FIXTURES = Path(__file__).parent / "fixtures" / "network"


@pytest.mark.parametrize("scenario", ["baseline", "existing", "future"])
def test_prepared_network_engine_acceptance(scenario: str, tmp_path: Path) -> None:
    """EPA 5.2.4 accepts prepared model text and both explicit scenario batches."""
    executable, library = os.environ.get("SWMM_ENGINE"), os.environ.get("SWMM_LIBRARY")
    if not executable or not library:
        pytest.skip("Set SWMM_ENGINE and SWMM_LIBRARY for pinned network compatibility checks")
    original = (FIXTURES / "baseline.inp").read_bytes()
    data = original
    if scenario != "baseline":
        instructions = json.loads((FIXTURES / f"{scenario}_changes.json").read_text(encoding="utf-8"))
        data = apply_changes(read_document(FIXTURES / "baseline.inp"), [Change(**row) for row in instructions]).data
    input_path = tmp_path / f"{scenario}.inp"
    input_path.write_bytes(data)
    result = check_engine(input_path, executable=executable, version_library=library,
                          expected_version=52004, output_directory=tmp_path)
    assert result.passed, result.errors
    assert result.engine_version == 52004
    assert input_path.read_bytes() == data
    assert (FIXTURES / "baseline.inp").read_bytes() == original
    assert result.report_path and result.report_path.is_file()
    assert result.output_path and result.output_path.is_file()
