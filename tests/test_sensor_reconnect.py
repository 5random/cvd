import asyncio
import json
import pytest

from program.src.data_handler.sources.sensor_source_manager import SensorManager
from program.src.data_handler.interface.sensor_interface import (
    SensorInterface,
    SensorReading,
    SensorStatus,
)
from src.utils.config_service import ConfigurationService


class FailingSensor(SensorInterface):
    def __init__(self, sensor_id: str, failures: int = 2):
        self._sensor_id = sensor_id
        self._initial_failures = failures
        self._remaining_failures = failures
        self.initialize_calls = 0
        self.cleanup_calls = 0
        self._is_connected = True

    async def initialize(self) -> bool:
        self.initialize_calls += 1
        if self.initialize_calls > 1:
            self._remaining_failures = 0
        self._is_connected = True
        return True

    async def read(self) -> SensorReading:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("fail")
        return SensorReading(self._sensor_id, 1.0, 0.0, SensorStatus.OK)

    async def configure(self, config):
        pass

    async def cleanup(self) -> None:
        self.cleanup_calls += 1
        self._is_connected = False

    @property
    def sensor_id(self) -> str:
        return self._sensor_id

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def sensor_type(self) -> str:
        return "dummy"


@pytest.mark.asyncio
async def test_sensor_reconnect(tmp_path, monkeypatch):
    cfg = {"sensor_reconnect_attempts": 2}
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default.json").write_text("{}")
    service = ConfigurationService(tmp_path / "config.json", tmp_path / "default.json")

    # silence logging
    monkeypatch.setattr(
        "program.src.data_handler.sources.sensor_source_manager.info", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "program.src.data_handler.sources.sensor_source_manager.warning", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "program.src.data_handler.sources.sensor_source_manager.error", lambda *a, **k: None
    )

    manager = SensorManager(service)
    sensor = FailingSensor("s1", failures=2)
    await manager.register_sensor(sensor)

    task = asyncio.create_task(manager._poll_sensor(sensor, 0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert sensor.cleanup_calls >= 1
    assert sensor.initialize_calls >= 1
    assert manager._failure_counts["s1"] == 0
    assert manager.get_sensor_reading("s1").status == SensorStatus.OK
