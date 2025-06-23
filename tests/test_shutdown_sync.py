import json
import asyncio
from cvd.utils.container import ApplicationContainer


def test_shutdown_sync_stops_polling_tasks(tmp_path):
    cfg = {
        "sensors": [
            {
                "sen1": {
                    "name": "Dummy",
                    "type": "temperature",
                    "interface": "serial",
                    "source": "mock_rs232",
                    "enabled": True,
                    "port": "COM1",
                    "channel": 0,
                    "poll_interval_ms": 10,
                }
            }
        ]
    }
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    (tmp_path / "default_config.json").write_text("{}")

    container = ApplicationContainer.create(tmp_path)
    asyncio.run(container.sensor_manager.start_all_configured_sensors())

    assert container.sensor_manager.get_active_sensors() == ["sen1"]

    container.shutdown_sync()

    assert container.sensor_manager.get_active_sensors() == []
