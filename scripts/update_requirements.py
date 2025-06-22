import sys
import tomllib
from pathlib import Path


def main() -> None:
    repo_dir = Path(__file__).resolve().parents[1]
    pyproject = repo_dir / "pyproject.toml"
    req_file = repo_dir / "requirements.txt"

    if not pyproject.exists():
        print("pyproject.toml not found", file=sys.stderr)
        sys.exit(1)

    try:
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        print(f"Error parsing {pyproject}: {e}", file=sys.stderr)
        sys.exit(1)

    deps = data.get("project", {}).get("dependencies", [])
    deps = sorted(deps)
    req_file.write_text("\n".join(deps) + "\n")


if __name__ == "__main__":
    main()
