from datetime import datetime
from pathlib import Path

from src.gui.gui_tab_components.gui_tab_base_component import ComponentConfig
from src.gui.gui_tab_components.gui_tab_data_component import (
    DataComponentConfig,
    DataFilesList,
)
from src.utils.data_utils.indexing import FileMetadata, DataCategory, FileStatus


class DummyManager:
    def __init__(self, files):
        self.files = files

    def list_files(self):
        return self.files


class DummyTable:
    def __init__(self):
        self.rows = []


class DummyLabel:
    def __init__(self):
        self.text = ""


class DummyButton:
    def __init__(self):
        self.disabled = False
        self.text = ""

    def disable(self):
        self.disabled = True

    def enable(self):
        self.disabled = False


# Helper to create simple file metadata


def _make_file(i):
    now = datetime.now()
    return FileMetadata(
        file_path=Path(f"file{i}.txt"),
        category=DataCategory.RAW,
        status=FileStatus.ACTIVE,
        size_bytes=100,
        created_at=now,
        modified_at=now,
    )


def test_pagination_resets_when_files_shrink(monkeypatch):
    initial_files = [_make_file(i) for i in range(6)]
    manager = DummyManager(initial_files)
    comp_config = ComponentConfig(component_id="test")
    data_config = DataComponentConfig(files_per_page=5)
    files_list = DataFilesList(comp_config, manager, data_config)

    # stub out ui elements used during update
    files_list._files_table = DummyTable()
    files_list._pagination_info = DummyLabel()
    files_list._prev_button = DummyButton()
    files_list._next_button = DummyButton()
    # avoid selection logic
    monkeypatch.setattr(files_list, "_update_selection_info", lambda: None)

    # initial load shows page 1
    files_list._load_files()
    assert len(files_list._files_table.rows) == 5

    # go to page 2 and refresh with fewer files
    files_list.current_page = 2
    manager.files = initial_files[:4]
    files_list._load_files()

    # pagination should reset to first page and table should not be empty
    assert files_list.current_page == 1
    assert len(files_list._files_table.rows) == 4


def test_table_selection_updates_state():
    manager = DummyManager([])
    comp_config = ComponentConfig(component_id="test")
    files_list = DataFilesList(comp_config, manager, DataComponentConfig())

    files_list._selection_info = DummyLabel()
    files_list._download_button = DummyButton()

    class Event:
        def __init__(self, selection):
            self.selection = selection

    files_list._on_table_select(Event(["a", "b"]))

    assert files_list.selected_files == {"a", "b"}
    assert files_list._download_button.disabled is False
