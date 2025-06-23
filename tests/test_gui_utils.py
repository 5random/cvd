import numpy as np
import pytest

from cvd.gui.utils import generate_mjpeg_stream

async def immediate(func, *args, **kwargs):
    return func(*args, **kwargs)

@pytest.mark.asyncio
async def test_generate_mjpeg_stream(monkeypatch):
    monkeypatch.setattr('cvd.gui.utils.run_in_executor', immediate)
    monkeypatch.setattr('cvd.gui.utils.cv2.imencode', lambda ext, frame: (True, np.array([1], dtype=np.uint8)))

    frames = [np.zeros((10, 10, 3), dtype=np.uint8)]

    async def frame_source():
        return frames.pop(0) if frames else None

    class DummyRequest:
        def __init__(self) -> None:
            self.disconnected = False

        async def is_disconnected(self):
            return self.disconnected

    req = DummyRequest()
    gen = generate_mjpeg_stream(frame_source, fps_cap=1000, timeout=0.01, request=req)

    chunk1 = await gen.__anext__()
    assert chunk1.startswith(b"--frame")

    chunk2 = await gen.__anext__()
    assert chunk2.startswith(b"--frame")

    chunk3 = await gen.__anext__()
    assert chunk3.startswith(b"--frame")

    req.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

