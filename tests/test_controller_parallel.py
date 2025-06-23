import asyncio
import time
import pytest

from src.controllers.controller_manager import ControllerManager
from src.controllers.controller_base import ControllerStage, ControllerConfig, ControllerResult

class SleepController(ControllerStage):
    def __init__(self, controller_id: str, config: ControllerConfig, delay: float, record: dict):
        super().__init__(controller_id, config)
        self.delay = delay
        self.record = record

    async def process(self, input_data):
        self.record.setdefault(self.controller_id, {})['start'] = time.perf_counter()
        await asyncio.sleep(self.delay)
        self.record[self.controller_id]['end'] = time.perf_counter()
        return ControllerResult.success_result({})

    async def initialize(self) -> bool:
        return True

    async def cleanup(self) -> None:
        pass

@pytest.mark.asyncio
async def test_process_data_parallel_execution_disabled():
    record = {}
    c1 = SleepController('c1', ControllerConfig('c1', 'custom'), 0.05, record)
    c2 = SleepController('c2', ControllerConfig('c2', 'custom'), 0.05, record)
    c3 = SleepController('c3', ControllerConfig('c3', 'custom'), 0.05, record)
    manager = ControllerManager(max_concurrency=2)
    manager.register_controller(c1)
    manager.register_controller(c2)
    manager.register_controller(c3)
    manager.add_dependency('c1', 'c3')
    manager.add_dependency('c2', 'c3')
    await manager.start_all_controllers()

    await manager.process_data({})
    await manager.stop_all_controllers()

    assert record['c2']['start'] >= record['c1']['end']
    assert record['c3']['start'] >= record['c2']['end']

@pytest.mark.asyncio
async def test_process_data_parallel_execution_enabled():
    record = {}
    c1 = SleepController('c1', ControllerConfig('c1', 'custom'), 0.05, record)
    c2 = SleepController('c2', ControllerConfig('c2', 'custom'), 0.05, record)
    c3 = SleepController('c3', ControllerConfig('c3', 'custom'), 0.05, record)
    manager = ControllerManager(max_concurrency=2, enable_parallel_execution=True)
    manager.register_controller(c1)
    manager.register_controller(c2)
    manager.register_controller(c3)
    manager.add_dependency('c1', 'c3')
    manager.add_dependency('c2', 'c3')
    await manager.start_all_controllers()

    await manager.process_data({})
    await manager.stop_all_controllers()

    # c1 and c2 should start very close in time
    diff = abs(record['c1']['start'] - record['c2']['start'])
    assert diff < 0.02
    assert record['c3']['start'] >= max(record['c1']['end'], record['c2']['end'])
