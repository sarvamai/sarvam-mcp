from __future__ import annotations

import json
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_server_json_versions_match_package_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    server = json.loads((ROOT / "server.json").read_text())

    package_version = pyproject["project"]["version"]

    assert server["version"] == package_version
    assert server["packages"][0]["version"] == package_version
