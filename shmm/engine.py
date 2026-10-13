"""Run an explicitly selected EPA SWMM engine as a separate compatibility check.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Manually maintained. Engine acceptance is not hydraulic equivalence or calibration.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from hashlib import sha256
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile


_ERROR_LINE = re.compile(r"^\s*ERROR\b.*$", flags=re.IGNORECASE | re.MULTILINE)
_VERSION = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$", flags=re.MULTILINE)


@dataclass(frozen=True, slots=True)
class EngineCheck:
    """Compatibility result and retained engine artifacts.

    Parameters
    ----------
    engine_version : int
        Pinned EPA version number, for example 52004 for 5.2.4.
    returncode : int
        Executable return code. EPA's executable can return zero on input errors.
    errors : tuple of str
        Report ERROR lines and execution/artifact failure diagnostics.
    report_text, stdout, stderr : str
        Captured diagnostic text; original report bytes remain on disk.
    report_path, output_path : Path or None
        Published artifacts when the engine produced them.
    input_sha256, report_sha256, output_sha256 : str or None
        SHA-256 checksums for the source and available engine artifacts.

    Notes
    -----
    Warnings remain in report_text and stdout and require engineering review.
    ``passed`` proves this engine completed without detected errors. It does
    not establish continuity tolerances, calibration, or unchanged hydraulics.
    """

    engine_version: int
    returncode: int
    errors: tuple[str, ...]
    report_text: str
    stdout: str
    stderr: str
    report_path: Path | None
    output_path: Path | None
    input_sha256: str
    report_sha256: str | None
    output_sha256: str | None

    @property
    def passed(self) -> bool:
        """Return whether execution and required artifacts passed the check."""
        return self.returncode == 0 and not self.errors


def _library_version(library_path: Path) -> int:
    """Query the supplied solver library without opening a model."""
    library = ctypes.CDLL(str(library_path))
    get_version = library.swmm_getVersion
    get_version.argtypes = []
    get_version.restype = ctypes.c_int
    return int(get_version())


def _decode(data: bytes) -> str:
    """Keep engine diagnostics readable without altering retained report bytes."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _run(arguments: list[str], directory: Path, timeout: float) -> subprocess.CompletedProcess[bytes]:
    """Run explicit arguments without a shell or inherited working directory."""
    return subprocess.run(
        arguments, cwd=directory, capture_output=True, timeout=timeout, check=False,
    )


def _publish_file(staged: Path, destination: Path) -> None:
    """Publish without replacing an existing destination on the same volume."""
    if os.name == "nt":
        # Windows rename fails if the destination exists; POSIX rename replaces.
        os.rename(staged, destination)
    else:
        os.link(staged, destination)


def check_engine(
    input_path: str | Path,
    *,
    executable: str | Path,
    version_library: str | Path,
    expected_version: int,
    output_directory: str | Path,
    timeout: float = 60,
) -> EngineCheck:
    """Run a pinned engine against an unchanged input and retain its diagnostics.

    Parameters
    ----------
    input_path : str or Path
        Existing INP file. Its bytes are checked before and after execution.
    executable, version_library : str or Path
        Explicit executable and solver library paths. No discovery or download.
        Both the library and executable version must match expected_version.
    expected_version : int
        Exact EPA version integer, for example 52004.
    output_directory : str or Path
        Existing directory for ``<input stem>.rpt`` and ``<input stem>.out``.
        Existing artifacts are never overwritten. Engine files are first
        generated in a private directory inside this directory.
    timeout : float, optional
        Positive timeout in seconds for each executable invocation. The version
        query and model execution each have this limit.

    Returns
    -------
    EngineCheck
        Explicit pass/failure result. Failed-model reports are retained too.

    Raises
    ------
    FileNotFoundError
        A required input, executable, library, or output directory is absent.
    FileExistsError
        A destination artifact already exists, including a concurrent creation.
    ValueError
        Invalid paths/settings, version mismatch, or changed source bytes.
    OSError
        The library cannot be loaded or the engine cannot be launched.
    subprocess.TimeoutExpired
        An engine invocation exceeds the timeout; incomplete staged artifacts
        are discarded and no result is published.

    Notes
    -----
    The process working directory is the input parent, so caller-prepared
    relative resources resolve consistently. The caller remains responsible
    for supplying those resources and the intended simulation.

    EPA's command wrapper returns zero even when the solver reports errors;
    report ERROR lines and required artifacts are checked separately. Output
    creation uses an atomic non-replacing Windows rename or POSIX hard link.
    A process crash
    during two-file publication can leave one artifact; the returned record
    exists only after complete publication. No run paths or environment
    variables are inferred by this library.
    """
    if isinstance(expected_version, bool) or not isinstance(expected_version, int) or expected_version <= 0:
        raise ValueError("expected_version must be a positive EPA integer version")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    source, engine, library, directory = (
        Path(path).resolve() for path in (input_path, executable, version_library, output_directory)
    )
    for path in (source, engine, library):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    report = directory / f"{source.stem}.rpt"
    binary = directory / f"{source.stem}.out"
    if len({source, engine, library, report, binary}) != 5:
        raise ValueError("Source, engine/library, report, and output paths must differ")
    for path in (report, binary):
        if path.exists():
            raise FileExistsError(path)

    source_bytes = source.read_bytes()
    actual_version = _library_version(library)
    if actual_version != expected_version:
        raise ValueError(f"Solver library version {actual_version} differs from expected {expected_version}")

    published: list[Path] = []
    try:
        version_process = _run([str(engine), "--version"], source.parent, timeout)
        version_text = _decode(version_process.stdout)
        version_matches = _VERSION.findall(version_text)
        if version_process.returncode != 0 or len(version_matches) != 1:
            raise ValueError("Executable --version did not return one recognizable EPA version")
        major, minor, build = (int(value) for value in version_matches[0])
        executable_version = major * 10000 + minor * 1000 + build
        if executable_version != expected_version:
            raise ValueError(f"Executable version {executable_version} differs from expected {expected_version}")

        with tempfile.TemporaryDirectory(prefix=".shmm-engine-", dir=directory) as stage_name:
            stage = Path(stage_name)
            staged_report, staged_binary = stage / report.name, stage / binary.name
            process = _run(
                [str(engine), str(source), str(staged_report), str(staged_binary)],
                source.parent, timeout,
            )
            stdout, stderr = _decode(process.stdout), _decode(process.stderr)
            report_bytes = staged_report.read_bytes() if staged_report.is_file() else None
            binary_bytes = staged_binary.read_bytes() if staged_binary.is_file() else None
            report_text = _decode(report_bytes) if report_bytes is not None else ""
            errors = [line.strip() for line in _ERROR_LINE.findall(report_text)]
            if process.returncode != 0:
                errors.append(f"Engine process exited with status {process.returncode}")
            if not report_bytes:
                errors.append("Engine did not create a nonempty report")
            if not errors and not binary_bytes:
                errors.append("Engine did not create nonempty binary results")
            # Check stdout as a fallback for wrappers that fail before a report.
            if "there are errors" in stdout.lower() and not errors:
                errors.append("Engine console reported errors without a report ERROR line")
            if source.read_bytes() != source_bytes:
                raise ValueError("Source model changed during engine execution")
            for staged_path, destination in ((staged_report, report), (staged_binary, binary)):
                if staged_path.is_file():
                    _publish_file(staged_path, destination)
                    published.append(destination)
            result = EngineCheck(
                actual_version, process.returncode, tuple(errors), report_text, stdout, stderr,
                report if report_bytes is not None else None,
                binary if binary_bytes is not None else None,
                sha256(source_bytes).hexdigest(),
                sha256(report_bytes).hexdigest() if report_bytes is not None else None,
                sha256(binary_bytes).hexdigest() if binary_bytes is not None else None,
            )
    except BaseException:
        for destination in reversed(published):
            destination.unlink(missing_ok=True)
        raise
    finally:
        if source.read_bytes() != source_bytes:
            for destination in reversed(published):
                destination.unlink(missing_ok=True)
            raise ValueError("Source model changed during engine check")
    return result
