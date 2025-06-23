import time
from types import SimpleNamespace


from cvd.gui.gui_elements.gui_live_plot_element import LivePlotComponent, PlotConfig
from cvd.data_handler.interface.sensor_interface import SensorReading, SensorStatus


class DummySensorManager:
    def __init__(self):
        self._readings = {}

    def set_reading(self, sensor_id, reading):
        self._readings[sensor_id] = reading

    def get_all_sensors(self):
        return list(self._readings.keys())

    def get_sensor_reading(self, sensor_id):
        return self._readings.get(sensor_id)


def create_component(max_points=5, refresh_rate_ms=1000):
    mgr = DummySensorManager()
    mgr.set_reading(
        "s1",
        SensorReading("s1", 1.0, time.time(), SensorStatus.OK, metadata={"unit": "C"}),
    )
    plot_config = PlotConfig(max_points=max_points, refresh_rate_ms=refresh_rate_ms)
    comp = LivePlotComponent(mgr, plot_config, sensors_to_display=["s1"])
    comp._initialize_series()
    return comp


def test_apply_settings_updates_deque_lengths():
    comp = create_component()
    # populate with some data
    for i in range(3):
        comp._data_store["s1"].append(i)
        comp._time_store.append(i)
    original_queue = comp._data_store["s1"]
    original_time_store = comp._time_store

    comp.plot_config.max_points = 2
    comp.plot_config.refresh_rate_ms = 2000
    comp._update_timer = SimpleNamespace(interval=0)
    dummy_dialog = SimpleNamespace(close=lambda: None)

    comp._apply_settings(dummy_dialog)

    assert comp._data_store["s1"].maxlen == 2
    assert list(comp._data_store["s1"]) == [1, 2]
    assert comp._data_store["s1"] is not original_queue

    expected_history = max(
        1, int(comp.plot_config.history_seconds * 1000 / comp.plot_config.refresh_rate_ms)
    )
    assert comp._time_store.maxlen == expected_history
    assert list(comp._time_store) == [0, 1, 2]
    assert comp._time_store is not original_time_store
