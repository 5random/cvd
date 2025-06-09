# Mixin providing shared methods for wizard components.
from typing import Any, Optional, Callable


class WizardMixin:
    """Common functionality for wizard-like GUI components."""

    _dialog: Optional[Any] = None
    on_close: Optional[Callable[[], None]] = None

    def _close_dialog(self) -> None:
        """Close the wizard dialog if open."""
        dialog = self._dialog  # type: Optional[Any]
        if dialog is not None:
            dialog.close()
            self._dialog = None

        callback = self.on_close  # type: Optional[Callable[[], None]]
        if callback:
            callback()

    def _update_element(self, data: Any) -> None:
        """Update element with new data (required by BaseComponent)."""
        # Wizards currently do not react to updates
        pass
