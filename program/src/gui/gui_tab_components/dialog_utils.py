"""Utility helpers for dialog-based components."""

from typing import Optional
from nicegui.elements.dialog import Dialog


class CancelableDialogMixin:
    """Mixin providing a standard :py:meth:`_cancel` implementation."""

    _dialog: Optional[Dialog] = None

    def _cancel(self) -> None:
        """Close the currently open dialog if any."""
        if self._dialog:
            self._dialog.close()
