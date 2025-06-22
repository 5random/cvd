import types

import pytest
from nicegui import ui

from src.gui.gui_tab_components.gui_tab_base_component import ComponentConfig
from src.gui.gui_tab_components.gui_tab_data_component import DataFilterPanel


def test_invalid_date_notifies(monkeypatch):
    messages = []
    monkeypatch.setattr(ui, "notify", lambda msg, **kwargs: messages.append(msg))
    panel = DataFilterPanel(ComponentConfig(component_id="test"), None, lambda _: None)
    panel._date_from_picker = types.SimpleNamespace(value="not-a-date")
    panel._date_to_picker = types.SimpleNamespace(value="")
    panel._apply_date_range()
    assert "Invalid date format" in messages[0]


def test_clear_filters_resets_date_pickers():
    panel = DataFilterPanel(ComponentConfig(component_id="test"), None, lambda _: None)
    panel._date_from_picker = types.SimpleNamespace(value="2023-01-01")
    panel._date_to_picker = types.SimpleNamespace(value="2023-01-02")
    panel.current_filters["date_range"] = (None, None)
    panel._clear_filters()
    assert panel._date_from_picker is None
    assert panel._date_to_picker is None
    panel._open_date_dialog()
    assert panel._date_from_picker.value == ""
    assert panel._date_to_picker.value == ""

