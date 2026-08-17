"""OBB (Opaque Binary Blob) expansion file metadata, as declared inside a `.xapk` archive."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ._bundle import _BaseBundle

__all__ = ["ObbFile"]


@dataclass(frozen=True, slots=True)
class ObbFile:
    """
    A single OBB expansion file bundled inside a `.xapk` archive, as declared by `manifest.json`'s
    `expansions` list.

    See the [expansion files guide](https://developer.android.com/google/play/expansion-files).

    >>> for obb in xapk.obb_files:
    ...     obb.extract(f"/tmp/{obb.name}")

    Attributes:
        name: The on-device filename (e.g. `"main.4.com.example.obb"`).
        is_patch: `True` for a `patch.*` expansion file (frequently-updated data), `False` for a
            `main.*` file (rarely-changed data) — inferred from `name`'s prefix.
        size: The size of the obb file's raw bytes, in bytes.
    """

    name: str
    is_patch: bool
    size: int
    _zip_name: str = field(repr=False, compare=False)
    _bundle: _BaseBundle = field(repr=False, compare=False)

    def read_bytes(self) -> bytes:
        """Read this obb file's raw bytes directly out of the bundle's archive."""
        return self._bundle._zip.read(self._zip_name)

    def extract(self, path: str | os.PathLike[str] | None = None) -> None:
        """
        Write this obb file's bytes to `path`.

        Args:
            path: Where to write the obb file. Defaults to `self.name` in the current working directory.
        """
        target = Path(path) if path is not None else Path.cwd() / self.name
        logger.debug("Extracting obb {} to {}", self.name, target)
        target.write_bytes(self.read_bytes())
