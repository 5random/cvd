from datetime import datetime
from pathlib import Path

from cvd.gui.gui_tab_components.gui_tab_base_component import ComponentConfig
from cvd.gui.gui_tab_components.gui_tab_data_component import (
    DataComponentConfig,
    DataFilesList,
)
from cvd.utils.data_utils.indexing import FileMetadata, DataCategory, FileStatus


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


def test_table_selection_updates_selected_files(monkeypatch):
    files = [_make_file(i) for i in range(3)]
    manager = DummyManager(files)
    comp_config = ComponentConfig(component_id="sel")
    data_config = DataComponentConfig(files_per_page=5)
    files_list = DataFilesList(comp_config, manager, data_config)

    files_list._files_table = DummyTable()
    files_list._pagination_info = DummyLabel()
    files_list._prev_button = DummyButton()
    files_list._next_button = DummyButton()
    files_list._load_files()

    called = {"count": 0}

    def fake_update():
        called["count"] += 1

    monkeypatch.setattr(files_list, "_update_selection_info", fake_update)

    selected_ids = [files_list._generate_file_id(f) for f in files[:2]]
    event = type("Event", (), {"value": selected_ids})()
    files_list._on_table_select(event)

    assert files_list.selected_files == set(selected_ids)
    assert called["count"] == 1


def test_table_selection_accepts_row_dicts(monkeypatch):
    files = [_make_file(i) for i in range(2)]
    manager = DummyManager(files)
    comp_config = ComponentConfig(component_id="sel2")
    data_config = DataComponentConfig(files_per_page=5)
    files_list = DataFilesList(comp_config, manager, data_config)

    files_list._files_table = DummyTable()
    files_list._pagination_info = DummyLabel()
    files_list._prev_button = DummyButton()
    files_list._next_button = DummyButton()
    files_list._load_files()

    called = {"count": 0}

    def fake_update():
        called["count"] += 1

    monkeypatch.setattr(files_list, "_update_selection_info", fake_update)

    selected_ids = [files_list._generate_file_id(f) for f in files[:1]]
    event = type("Event", (), {"selection": [{"id": selected_ids[0]}]})()
    files_list._on_table_select(event)

    assert files_list.selected_files == set(selected_ids)
    assert called["count"] == 1


def test_download_selected_files_calls_data_manager(tmp_path, monkeypatch):
    files = [_make_file(i) for i in range(2)]
    for meta in files:
        fpath = tmp_path / meta.file_path.name
        fpath.write_text("x")
        meta.file_path = fpath

    manager = DummyManager(files)
    comp_config = ComponentConfig(component_id="dl")
    data_config = DataComponentConfig(files_per_page=5)
    files_list = DataFilesList(comp_config, manager, data_config)

    files_list._files_table = DummyTable()
    files_list._pagination_info = DummyLabel()
    files_list._prev_button = DummyButton()
    files_list._next_button = DummyButton()
    files_list._download_status = DummyLabel()
    files_list._load_files()

    ids = [files_list._generate_file_id(f) for f in files]
    files_list.selected_files = set(ids)

    captured = {}

    def fake_create(paths, format="zip"):
        captured["paths"] = paths
        return "req-1"

    monkeypatch.setattr(manager, "create_download_package", fake_create, raising=False)

    started = {}

    def fake_start(req_id):
        started["id"] = req_id

    monkeypatch.setattr(files_list, "_start_download_monitoring", fake_start)

    from nicegui import ui

    monkeypatch.setattr(ui, "notify", lambda *a, **k: None)
    monkeypatch.setattr(ui, "download", lambda *a, **k: None)

    files_list._download_selected_files()

    expected_paths = {str(f.file_path.resolve()) for f in files}
    assert set(captured.get("paths")) == expected_paths
    assert started.get("id") == "req-1"
