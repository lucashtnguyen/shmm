"""Edit finished SWMM records using hymo's read-only document interface.

Last modified by: Lucas HT Nguyen
Contact: https://github.com/lucashtnguyen
Date: 2026-10-16
Notes: Manually maintained; legacy table APIs load only on request.
"""

from importlib import import_module
from typing import Any

from .editing import Change, ChangeResult, apply_changes, edit_model, preview_changes
from .geometry import VertexChange
from .comparison import ModelDiff, compare_written_model, preview_model_diff, write_diff_reports
from .spatial import GISAnnotation, GISFlag, export_shapefiles
from .sections import (SectionPatch, SectionPatchResult, compare_written_sections,
                       preview_section_patches, publish_section_patches)

__author__ = "Lucas HT Nguyen"
__email__ = ""
__contact__ = "https://github.com/lucashtnguyen"
__version__ = "0.1.2"
__all__ = ["Change", "ChangeResult", "VertexChange", "ModelDiff", "apply_changes", "preview_changes", "edit_model",
           "preview_model_diff", "compare_written_model", "write_diff_reports",
           "GISAnnotation", "GISFlag", "export_shapefiles", "SectionPatch", "SectionPatchResult",
           "preview_section_patches", "compare_written_sections", "publish_section_patches"]


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
