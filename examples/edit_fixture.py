"""Edit-and-run example for the neutral network acceptance fixtures.

Author: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained. Edit SETTINGS below in VS Code, then run this
file. Preparation and anonymization are external to this repository.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from hymo import read_document
from shmm import Change, edit_model, preview_changes

# These example settings are explicit test choices, not project configuration.
SCENARIO = "existing"  # "existing" or "future"
REVIEWED_ONLY = False  # True excludes explicitly synthetic addition examples.
DEBUG = False


def main() -> None:
    """Preview fixture instructions and publish a separate candidate plus audit."""
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format="%(levelname)s: %(message)s")
    if SCENARIO not in {"existing", "future"}:
        raise ValueError("SCENARIO must be existing or future")
    repository = Path(__file__).resolve().parents[1]
    fixture = repository / "tests" / "fixtures" / "network"
    prefix = "reviewed_" if REVIEWED_ONLY else ""
    instructions = json.loads((fixture / f"{prefix}{SCENARIO}_changes.json").read_text(encoding="utf-8"))
    changes = [Change(**instruction) for instruction in instructions]
    source = fixture / "baseline.inp"
    preview = preview_changes(read_document(source), changes)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    destination = repository / ".cache" / "fixture_demo" / f"{SCENARIO}_{run_id}"
    destination.mkdir(parents=True, exist_ok=False)
    result = edit_model(source, changes, destination / "candidate.inp", destination / "audit.json",
                        expected_hash=preview.audit["baseline_sha256"])
    if result.data != preview.data:
        raise RuntimeError("Published candidate differs from preview")
    logging.info("%s: %d instructions; output %s", SCENARIO, len(changes), destination)
    logging.info("Engine check: %s", result.audit["engine_check"])


if __name__ == "__main__":
    main()
