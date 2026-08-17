"""Small helpers shared by more than one module (kept out of `_apk.py`/`_bundle.py` to avoid an import cycle)."""

from __future__ import annotations

import re

__all__ = ["sanitize_filename_component"]

# Characters illegal in a Windows filename (`<>:"/\|?*` + control chars) — POSIX itself only
# forbids `/` and NUL, but `rename()`'s `{attr}` fields can carry arbitrary apk-controlled text
# (e.g. `version_name`), so formatting a name that works on Linux but raises `OSError` the moment
# the same code runs on Windows is a real, previously-unhandled portability trap.
_ILLEGAL_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_component(value: str) -> str:
    """Replace characters illegal in a Windows (or, for `/`, POSIX) filename with `_`."""
    return _ILLEGAL_FILENAME_CHARS.sub("_", value)
