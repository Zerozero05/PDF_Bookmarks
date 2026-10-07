"""Stable application identity, independent of executable names and locations."""

from dataclasses import dataclass
import importlib
from pathlib import Path
import re
import sys

from config_manager import CONFIG_SCHEMA


APP_ID = "com.linzh.PDFBookmarks"
UPDATE_SCHEMA = 1
UPDATE_CHANNEL = "stable"


@dataclass(frozen=True, slots=True)
class BuildInfo:
    app_id: str
    version: str
    variant: str
    update_schema: int = UPDATE_SCHEMA
    config_schema: int = CONFIG_SCHEMA
    channel: str = UPDATE_CHANNEL
    entrypoint: str = "gui"

    def __post_init__(self):
        if self.app_id != APP_ID:
            raise ValueError("Unknown application identity")
        if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", self.version):
            raise ValueError("Build version must be a stable semantic version")
        if self.variant not in {"single", "portable"}:
            raise ValueError("Build variant must be single or portable")
        if self.update_schema != UPDATE_SCHEMA or self.config_schema != CONFIG_SCHEMA:
            raise ValueError("Unsupported build schema")
        if self.channel != UPDATE_CHANNEL:
            raise ValueError("Unsupported build channel")
        if self.entrypoint not in {"gui", "cli", "updater", "source"}:
            raise ValueError("Unsupported build entrypoint")


def get_build_info():
    """Read the module generated and embedded by scripts/build_windows.py.

    Source runs use VERSION for display/testing, but the updater separately
    rejects installation unless sys.frozen is true. A frozen build missing its
    identity must fail closed rather than infer a variant from its filename.
    """
    try:
        identity = importlib.import_module("_build_identity")
    except ModuleNotFoundError as error:
        if error.name != "_build_identity":
            raise
        if getattr(sys, "frozen", False):
            raise RuntimeError("Frozen application is missing its build identity") from error
        version = (Path(__file__).resolve().parent / "VERSION").read_text(encoding="utf-8").strip()
        variant = "single"
        entrypoint = "source"
    else:
        version = identity.APP_VERSION
        variant = identity.BUILD_VARIANT
        entrypoint = identity.BUILD_ENTRYPOINT
    return BuildInfo(APP_ID, version, variant, entrypoint=entrypoint)


def can_self_update():
    """Only frozen GUI builds install GUI assets; CLI/source runs stay intact."""
    if not getattr(sys, "frozen", False):
        return False
    identity = importlib.import_module("_build_identity")
    return getattr(identity, "BUILD_ENTRYPOINT", None) == "gui"


APP_VERSION = get_build_info().version
