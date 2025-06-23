from datetime import datetime, date
import types


from cvd.experiment_manager import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentState,
)
from cvd.gui.gui_tab_components.gui_tab_experiment_component import (
    ExperimentHistoryTable,
)


class DummyManager:
    def __init__(self, exps):
        self.exps = exps

    def list_experiments(self):
        return list(self.exps.keys())

    def get_experiment_config(self, eid):
        return self.exps[eid]["config"]

    def get_experiment_result(self, eid):
        return self.exps[eid]["result"]


class DummyTable:
    def __init__(self):
        self.rows = []
        self.pagination = {"sortBy": None, "descending": False}


# helper to create a result


def _make_result(eid, name, state, ts):
    return ExperimentResult(
        experiment_id=eid,
        name=name,
        state=state,
        start_time=ts,
        duration_seconds=10.0,
        data_points_collected=1,
    )


def _create_table():
    exps = {
        "e1": {
            "config": ExperimentConfig(name="Alpha"),
            "result": _make_result(
                "e1", "Alpha", ExperimentState.COMPLETED, datetime(2023, 1, 1)
            ),
        },
        "e2": {
            "config": ExperimentConfig(name="Beta"),
            "result": _make_result(
                "e2", "Beta", ExperimentState.RUNNING, datetime(2023, 3, 1)
            ),
        },
        "e3": {
            "config": ExperimentConfig(name="Charlie"),
            "result": _make_result(
                "e3", "Charlie", ExperimentState.COMPLETED, datetime(2023, 2, 1)
            ),
        },
    }
    mgr = DummyManager(exps)
    table = ExperimentHistoryTable(mgr)
    table._table = DummyTable()
    return table


def test_filters_reduce_rows():
    table = _create_table()
    table._name_filter = "ha"
    table._state_filter = ExperimentState.COMPLETED
    table._from_date = date(2023, 2, 1)
    table._load_experiments()
    assert len(table._table.rows) == 1
    assert table._table.rows[0]["name"] == "Charlie"


def test_sorting_applied():
    table = _create_table()
    table._table.pagination["sortBy"] = "name"
    table._table.pagination["descending"] = True
    table._load_experiments()
    names = [r["name"] for r in table._table.rows]
    assert names == ["Charlie", "Beta", "Alpha"]

def test_clear_filters_resets_date_pickers():
    table = _create_table()
    table._date_from_picker = types.SimpleNamespace(value="2023-01-01")
    table._date_to_picker = types.SimpleNamespace(value="2023-01-02")
    table._from_date = date(2023, 1, 1)
    table._to_date = date(2023, 1, 2)
    table._clear_filters()
    assert table._date_from_picker is None
    assert table._date_to_picker is None
    table._open_date_dialog()
    assert table._date_from_picker.value == ""
    assert table._date_to_picker.value == ""
