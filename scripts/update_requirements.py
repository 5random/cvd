import tomllib
from pathlib import Path


def main() -> None:
    repo_dir = Path(__file__).resolve().parents[1]
    pyproject = repo_dir / "pyproject.toml"
    req_file = repo_dir / "requirements.txt"

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    deps = data.get("project", {}).get("dependencies", [])
    deps = sorted(deps)
    req_file.write_text("\n".join(deps) + "\n")


if __name__ == "__main__":
    main()
