"""Edit finished SWMM records using hymo's read-only document interface.

Last modified by: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-13
Notes: Manually maintained; legacy table APIs load only on request.
"""

from importlib import import_module
from typing import Any

from .editing import Change, ChangeResult, apply_changes, edit_model, preview_changes

__author__ = "Lucas HT Nguyen"
__email__ = ""
__contact__ = "https://github.com/lucashtnguyen"
__version__ = "0.1.0"
__all__ = ["Change", "ChangeResult", "apply_changes", "preview_changes", "edit_model"]


def __getattr__(name: str) -> Any:
    """Load historical APIs without eagerly importing GIS or test dependencies."""
    if name == "INP":
        return import_module(".inp", __name__).INP
    if name == "load_template":
        return import_module(".shmm", __name__).load_template
    if name in {"gis", "utils"}:
        return import_module(f".{name}", __name__)
    if name == "test":
        return import_module(".tests", __name__).test
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
