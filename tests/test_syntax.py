import subprocess
import py_compile
from pathlib import Path

import pytest


def list_python_files() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "*.py"], text=True)
    files = []
    for line in out.splitlines():
        path = Path(line)
        if "legacy_stuff" in path.parts:
            continue
        files.append(line)
    return files


@pytest.mark.parametrize("path", list_python_files())
def test_python_syntax(path: str) -> None:
    py_compile.compile(path, doraise=True)
