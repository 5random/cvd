from setuptools import setup, find_packages
from glob import glob
from pathlib import Path
import tomllib


def read_dependencies() -> list[str]:
    """Load dependencies from pyproject.toml."""
    pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("dependencies", [])

setup(
    name='cvd',
    version='0.1.0',
    install_requires=read_dependencies(),
    packages=find_packages(where="src"),
    package_dir={"": "src"},

    data_files=[
        ("cvd/config", glob("config/*.json")),
        ("cvd/data", ["data/data_index.json"]),
        ("cvd/data/logs", glob("data/logs/*.log")),
        ("cvd/data/notifications", glob("data/notifications/*.json")),
    ],
)
