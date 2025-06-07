import pytest

from src.data_handler.processing.pipeline.pipeline import DataPipeline
from src.data_handler.processing.processing_base import ProcessingStage, ProcessingResult

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
