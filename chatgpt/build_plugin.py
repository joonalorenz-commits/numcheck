"""
Build the ChatGPT/Codex plugin ZIP: chatgpt/plugin/ plus the numcheck package
copied into the skill's scripts folder.

    python chatgpt/build_plugin.py      -> chatgpt/dist/numcheck-plugin-<version>.zip
"""

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "chatgpt" / "plugin"
DIST = ROOT / "chatgpt" / "dist"


def main() -> Path:
    version = json.loads((PLUGIN / "plugin.json").read_text())["version"]
    DIST.mkdir(exist_ok=True)
    out = DIST / f"numcheck-plugin-{version}.zip"
    package = ROOT / "src" / "numcheck"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PLUGIN.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.name != ".DS_Store":
                z.write(f, f.relative_to(PLUGIN).as_posix())
        for f in sorted(package.rglob("*.py")):
            z.write(f, "skills/numcheck/scripts/numcheck/" + f.relative_to(package).as_posix())
    print(out)
    return out


if __name__ == "__main__":
    main()
