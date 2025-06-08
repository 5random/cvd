"""Helper utilities for NiceGUI UI functions."""

from nicegui import ui


def notify_later(message: str, **kwargs) -> None:
    """Display a notification asynchronously using :func:`nicegui.ui.timer`."""
    ui.timer(0, lambda: ui.notify(message, **kwargs), once=True)


__all__ = ["notify_later"]
