"""File operations: new model, open, save."""

from __future__ import annotations

from pathlib import Path

from ..enums import Units
from ._base import Manager


class Files(Manager):
    """Create, open and save SAP2000 models. Wraps ``cFile``."""

    def new_blank(self, *, units: Units | None = None) -> None:
        """Initialize a new blank model, optionally setting the database units.

        Wraps: ``SapModel.InitializeNewModel`` + ``File.NewBlank``.
        """
        if units is not None:
            self._g.call(self._raw.InitializeNewModel, int(units), api_name="InitializeNewModel")
        self._g.call(self._raw.File.NewBlank, api_name="File.NewBlank")

    def open(self, path: str | Path) -> None:
        """Open an existing ``.sdb`` model. Wraps ``File.OpenFile``."""
        self._g.call(self._raw.File.OpenFile, str(path), api_name="File.OpenFile")

    def save(self, path: str | Path | None = None) -> None:
        """Save the model. With ``path`` does a save-as. Wraps ``File.Save``.

        ``File.Save("")`` saves to the current file; pass a path to save-as.
        """
        target = "" if path is None else str(path)
        self._g.call(self._raw.File.Save, target, api_name="File.Save")
