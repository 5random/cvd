import builtins
import pytest
from scripts import update_requirements


def test_update_requirements(tmp_path, monkeypatch):
    deps = ["foo==1.0", "bar>=2.0"]
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project]
dependencies = [
    \"foo==1.0\",
    \"bar>=2.0\",
]
"""
    )
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(
        update_requirements, "__file__", str(scripts_dir / "update_requirements.py")
    )
    update_requirements.main()
    req_file = tmp_path / "requirements.txt"

    assert req_file.read_text().splitlines() == sorted(deps)

def test_update_requirements_missing_file(tmp_path, monkeypatch):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(update_requirements, "__file__", str(scripts_dir / "update_requirements.py"))
    with pytest.raises(SystemExit) as exc:
        update_requirements.main()
    assert exc.value.code != 0


def test_update_requirements_bad_toml(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("invalid = [")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(update_requirements, "__file__", str(scripts_dir / "update_requirements.py"))
    with pytest.raises(SystemExit) as exc:
        update_requirements.main()
    assert exc.value.code != 0
