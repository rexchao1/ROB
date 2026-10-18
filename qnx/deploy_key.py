"""Select the opt-in Pi credentials without sourcing shell code or logging values.

Only deploy.sh invokes this, with stdout redirected to a private temporary file.
"""
from pathlib import Path
import sys

NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_WORKSPACE_ID")


def selected(path: Path) -> str:
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.strip().removeprefix("export ")
        name, sep, value = line.partition("=")
        if sep and name.strip() in NAMES:
            values[name.strip()] = value.strip().strip("\"'")
    if not values.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY is missing from .env.local")
    return "".join(f"{name}={values[name]}\n" for name in NAMES if values.get(name))


if __name__ == "__main__":
    try:
        content = selected(Path(sys.argv[1]))
    except (OSError, ValueError):
        print("deploy: --with-key requires ANTHROPIC_API_KEY in .env.local", file=sys.stderr)
        sys.exit(2)
    sys.stdout.write(content)
