import numpy as np
import pytest

from src.gui.utils import generate_mjpeg_stream

async def immediate(func, *args, **kwargs):
    return func(*args, **kwargs)

@pytest.mark.asyncio
async def test_generate_mjpeg_stream(monkeypatch):
    monkeypatch.setattr('src.gui.utils.run_camera_io', immediate)
    monkeypatch.setattr('src.gui.utils.cv2.imencode', lambda ext, frame: (True, np.array([1], dtype=np.uint8)))

    frames = [np.zeros((10, 10, 3), dtype=np.uint8)]

    async def frame_source():
        return frames.pop(0) if frames else None

    gen = generate_mjpeg_stream(frame_source, fps_cap=1000, timeout=0.01)
    chunk1 = await gen.__anext__()
    assert chunk1.startswith(b"--frame")
    chunk2 = await gen.__anext__()
    assert chunk2.startswith(b"--frame")
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

