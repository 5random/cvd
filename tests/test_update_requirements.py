import builtins
from scripts import update_requirements


def test_update_requirements(tmp_path, monkeypatch):
    deps = ["foo==1.0", "bar>=2.0"]
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""[project]
dependencies = [
    \"foo==1.0\",
    \"bar>=2.0\",
]
""")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(update_requirements, "__file__", str(scripts_dir / "update_requirements.py"))
    update_requirements.main()
    req_file = tmp_path / "requirements.txt"
    assert req_file.read_text().splitlines() == deps
