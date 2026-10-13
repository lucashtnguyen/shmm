"""Check pinned SWMM execution, diagnostics, preservation, and artifact safety.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Manually maintained. Real engine tests require explicit environment opt-in.
"""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Callable
from unittest.mock import Mock

import pytest

import shmm.engine as engine


SMOKE_MODEL = (
    b"; Synthetic engine compatibility fixture\n"
    b"; Author: Lucas HT Nguyen; Contact: https://github.com/lucashtnguyen; Date: 2026-10-13\n"
    b"[TITLE]\nSynthetic engine smoke model\n"
    b"[OPTIONS]\nFLOW_UNITS CFS\nFLOW_ROUTING DYNWAVE\n"
    b"START_DATE 01/01/2020\nSTART_TIME 00:00:00\n"
    b"END_DATE 01/01/2020\nEND_TIME 01:00:00\n"
    b"REPORT_START_DATE 01/01/2020\nREPORT_START_TIME 00:00:00\n"
    b"ROUTING_STEP 00:00:01\nREPORT_STEP 00:05:00\n"
    b"[JUNCTIONS]\nN1 10 5 0 0 0\n"
    b"[OUTFALLS]\nO1 9 FREE NO\n"
    b"[CONDUITS]\nP1 N1 O1 100 0.013 0 0 0 0\n"
    b"[XSECTIONS]\nP1 CIRCULAR 1 0 0 0 1\n"
    b"[DWF]\nN1 FLOW 0.1\n"
    b"[REPORT]\nINPUT NO\nCONTINUITY YES\nFLOWSTATS YES\nNODES ALL\nLINKS ALL\n"
)


@pytest.fixture
def paths(tmp_path: Path) -> dict[str, Path]:
    """Create explicit source/tools/output paths without external dependencies."""
    source = tmp_path / "synthetic.inp"
    executable = tmp_path / "runswmm.exe"
    library = tmp_path / "swmm5.dll"
    output = tmp_path / "results"
    source.write_bytes(SMOKE_MODEL)
    executable.write_bytes(b"mock executable")
    library.write_bytes(b"mock library")
    output.mkdir()
    return {"input_path": source, "executable": executable,
            "version_library": library, "output_directory": output}


def mock_solver(
    monkeypatch: pytest.MonkeyPatch,
    *,
    report: bytes | None = b"EPA SWMM 5.2 (Build 5.2.4)\nSimulation complete\n",
    binary: bytes | None = b"mock binary results",
    returncode: int = 0,
    library_version: int = 52004,
    executable_version: bytes = b"\n5.2.4\n",
    on_run: Callable[[list[str]], None] | None = None,
) -> Mock:
    """Mock both version queries and model execution with inspectable arguments."""
    get_version = Mock(return_value=library_version)
    monkeypatch.setattr(engine.ctypes, "CDLL", lambda path: SimpleNamespace(swmm_getVersion=get_version))

    def run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        if arguments[-1] == "--version":
            return subprocess.CompletedProcess(arguments, 0, executable_version, b"")
        if on_run:
            on_run(arguments)
        if report is not None:
            Path(arguments[2]).write_bytes(report)
        if binary is not None:
            Path(arguments[3]).write_bytes(binary)
        return subprocess.CompletedProcess(arguments, returncode, b"engine console", b"")

    process = Mock(side_effect=run)
    monkeypatch.setattr(engine.subprocess, "run", process)
    return process


def test_mocked_engine_pins_both_versions_and_retains_hashed_outputs(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful check uses explicit paths and preserves every source byte."""
    process = mock_solver(monkeypatch)
    result = engine.check_engine(**paths, expected_version=52004)
    assert result.passed
    assert result.engine_version == 52004
    assert result.input_sha256 == sha256(SMOKE_MODEL).hexdigest()
    assert paths["input_path"].read_bytes() == SMOKE_MODEL
    assert result.report_path == paths["output_directory"] / "synthetic.rpt"
    assert result.output_path == paths["output_directory"] / "synthetic.out"
    assert result.report_sha256 == sha256(result.report_path.read_bytes()).hexdigest()
    assert result.output_sha256 == sha256(result.output_path.read_bytes()).hexdigest()
    assert process.call_count == 2
    arguments, kwargs = process.call_args
    assert arguments[0][1] == str(paths["input_path"])
    assert kwargs["cwd"] == paths["input_path"].parent
    assert kwargs["timeout"] == 60
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert not list(paths["output_directory"].glob(".shmm-engine-*"))


def test_report_errors_fail_even_when_executable_returns_zero(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EPA's zero exit status cannot hide a failed model or missing endpoint."""
    mock_solver(monkeypatch, report=b"EPA SWMM\n  ERROR 209: undefined object MISSING\n", binary=None)
    result = engine.check_engine(**paths, expected_version=52004)
    assert not result.passed
    assert result.returncode == 0
    assert result.errors == ("ERROR 209: undefined object MISSING",)
    assert result.report_path.is_file()
    assert result.output_path is None


@pytest.mark.parametrize("report,binary,returncode", [
    (None, None, 4), (b"", None, 0), (b"Simulation complete", None, 0),
])
def test_missing_artifacts_and_process_failures_are_explicit(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
    report: bytes | None, binary: bytes | None, returncode: int,
) -> None:
    """Failures stay observable even without a solver-generated ERROR line."""
    mock_solver(monkeypatch, report=report, binary=binary, returncode=returncode)
    result = engine.check_engine(**paths, expected_version=52004)
    assert not result.passed
    assert result.errors


@pytest.mark.parametrize("library_version,executable_version", [
    (51015, b"5.2.4"), (52004, b"5.1.15"), (52004, b"unrecognized version"),
])
def test_version_mismatches_reject_before_model_execution(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
    library_version: int, executable_version: bytes,
) -> None:
    """A version library does not establish a differently built executable."""
    process = mock_solver(monkeypatch, library_version=library_version,
                          executable_version=executable_version)
    with pytest.raises(ValueError, match="version"):
        engine.check_engine(**paths, expected_version=52004)
    assert process.call_count <= 1
    assert list(paths["output_directory"].iterdir()) == []


def test_existing_output_is_never_overwritten(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Output collisions are rejected before launching the engine."""
    process = mock_solver(monkeypatch)
    existing = paths["output_directory"] / "synthetic.rpt"
    existing.write_bytes(b"existing human review")
    with pytest.raises(FileExistsError):
        engine.check_engine(**paths, expected_version=52004)
    assert existing.read_bytes() == b"existing human review"
    assert process.call_count == 0


def test_concurrent_output_creation_is_preserved(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late binary collision rolls back only this check's published report."""
    mock_solver(monkeypatch)
    publish = engine._publish_file

    def concurrent(staged: Path, destination: Path) -> None:
        if destination.suffix == ".out":
            destination.write_bytes(b"concurrent user results")
        publish(staged, destination)

    monkeypatch.setattr(engine, "_publish_file", concurrent)
    with pytest.raises(FileExistsError):
        engine.check_engine(**paths, expected_version=52004)
    assert not (paths["output_directory"] / "synthetic.rpt").exists()
    assert (paths["output_directory"] / "synthetic.out").read_bytes() == b"concurrent user results"


def test_source_change_prevents_publication(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check snapshot integrity before publishing any engine artifacts."""
    mock_solver(monkeypatch, on_run=lambda arguments: Path(arguments[1]).write_bytes(b"changed input"))
    with pytest.raises(ValueError, match="Source model changed"):
        engine.check_engine(**paths, expected_version=52004)
    assert list(paths["output_directory"].iterdir()) == []


def test_timeout_leaves_no_published_artifacts(
    paths: dict[str, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout cleanup does not mistake an incomplete run for engine acceptance."""
    def timeout(arguments: list[str]) -> None:
        raise subprocess.TimeoutExpired(arguments, 0.01)

    mock_solver(monkeypatch, on_run=timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        engine.check_engine(**paths, expected_version=52004, timeout=0.01)
    assert list(paths["output_directory"].iterdir()) == []


@pytest.mark.parametrize("setting,value", [
    ("expected_version", 0), ("expected_version", True),
    ("timeout", 0), ("timeout", float("nan")),
])
def test_invalid_check_settings_fail_early(
    paths: dict[str, Path], setting: str, value: object,
) -> None:
    """Explicit pins and timeout contracts reject invalid configuration."""
    arguments = {**paths, "expected_version": 52004, setting: value}
    with pytest.raises(ValueError):
        engine.check_engine(**arguments)


@pytest.mark.parametrize("invalid_endpoint", [False, True])
def test_optional_real_epa_524_smoke(tmp_path: Path, invalid_endpoint: bool) -> None:
    """Opt in to one valid and one invalid model using explicitly supplied tools."""
    executable, library = os.environ.get("SWMM_ENGINE"), os.environ.get("SWMM_LIBRARY")
    if not executable or not library:
        pytest.skip("Set SWMM_ENGINE and SWMM_LIBRARY explicitly to enable pinned 5.2.4 smoke tests")
    source = tmp_path / "synthetic.inp"
    data = SMOKE_MODEL.replace(b"P1 N1 O1", b"P1 N1 MISSING") if invalid_endpoint else SMOKE_MODEL
    source.write_bytes(data)
    output = tmp_path / "results"
    output.mkdir()
    result = engine.check_engine(source, executable=executable, version_library=library,
                                 expected_version=52004, output_directory=output)
    assert result.engine_version == 52004
    assert source.read_bytes() == data
    if invalid_endpoint:
        assert not result.passed
        assert any("209" in error and "MISSING" in error for error in result.errors)
    else:
        assert result.passed, result.errors
        assert result.report_sha256
        assert result.output_sha256
