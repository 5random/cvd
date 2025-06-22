import importlib
import importlib.metadata

from importlib.metadata import EntryPoint, EntryPoints

# Dummy sensor factory used for the entry point


def dummy_sensor_factory(config, executor=None):
    return None


def test_entry_point_registration(monkeypatch):
    ep = EntryPoint(
        name="dummy",
        value="tests.test_sensor_entry_points:dummy_sensor_factory",
        group="cvd.sensors",
    )
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda: EntryPoints([ep]),
    )
    from src.data_handler.sources import sensor_source_manager as manager

    importlib.reload(manager)
    # Reload may return the existing module due to src/program aliasing.
    # After applying the monkeypatch and reloading the module, explicitly
    # load entry point sensors so the dummy factory is registered.
    manager.load_entry_point_sensors()

    assert "dummy" in manager.SENSOR_REGISTRY
    assert manager.SENSOR_REGISTRY["dummy"] is dummy_sensor_factory
