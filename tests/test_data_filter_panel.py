import types

import pytest
from nicegui import ui

from src.gui.gui_tab_components.gui_tab_base_component import ComponentConfig
from src.gui.gui_tab_components.gui_tab_data_component import DataFilterPanel


def test_invalid_date_notifies(monkeypatch):
    messages = []
    monkeypatch.setattr(ui, 'notify', lambda msg, **kwargs: messages.append(msg))
    panel = DataFilterPanel(ComponentConfig(component_id="test"), None, lambda _: None)
    panel._open_date_dialog()
    panel._date_from_picker.value = "not-a-date"
    panel._apply_date_range()
    assert "Invalid date format" in messages[0]
