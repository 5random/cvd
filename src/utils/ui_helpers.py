"""Helper utilities for NiceGUI UI functions."""

from typing import Optional

from nicegui import ui
from nicegui.element import Element


def notify_later(message: str, *, slot: Optional[Element] = None, **kwargs) -> None:
    """Display a notification asynchronously using :func:`nicegui.ui.timer`.

    Args:
        message: The notification message.
        slot: Optional container slot to execute the timer within.
        **kwargs: Additional keyword arguments passed to :func:`ui.notify`.
    """

    if slot is not None:
        with slot:
            ui.timer(0, lambda: ui.notify(message, **kwargs), once=True)
    else:
        ui.timer(0, lambda: ui.notify(message, **kwargs), once=True)


__all__ = ["notify_later"]
