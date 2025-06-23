import pytest

from cvd.data_handler.processing.pipeline.pipeline import DataPipeline
from cvd.data_handler.processing.processing_base import ProcessingStage, ProcessingResult

class AddOneStage(ProcessingStage):
    async def process(self, data):
        return ProcessingResult.success_result(data + 1)

class FailingStage(ProcessingStage):
    async def process(self, data):
        return ProcessingResult.error_result("fail")

@pytest.mark.asyncio
async def test_pipeline_add_remove_and_process():
    pipe = DataPipeline("p1")
    stage = AddOneStage("s1")
    pipe.add_stage(stage)
    assert pipe.get_stage("s1") is stage
    result = await pipe.process(1)
    assert result.success and result.data == 2
    assert pipe.remove_stage("s1") is True
    assert pipe.get_stage("s1") is None

@pytest.mark.asyncio
async def test_pipeline_process_error():
    pipe = DataPipeline("p2")
    pipe.add_stage(FailingStage("fail"))
    result = await pipe.process(1)
    assert not result.success

@pytest.mark.asyncio
async def test_pipeline_clear_stats_resets_stage_stats():
    pipe = DataPipeline("p3")
    s1 = AddOneStage("s1")
    s2 = FailingStage("s2")
    pipe.add_stage(s1)
    pipe.add_stage(s2)

    result = await pipe.process(1)
    assert not result.success
    assert s1._processing_time > 0
    assert s2._processing_time > 0
    assert s2._error_count == 1

    pipe.clear_stats()

    assert pipe.get_pipeline_stats()["total_processed"] == 0
    assert pipe.get_pipeline_stats()["total_errors"] == 0
    assert s1._processing_time == 0.0
    assert s2._processing_time == 0.0
    assert s1._error_count == 0
    assert s2._error_count == 0
