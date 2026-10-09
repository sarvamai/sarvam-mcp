from __future__ import annotations

import json
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SERVER_JSON = _REPO_ROOT / "server.json"


def test_server_json_version_matches_pyproject():
    """server.json is registry metadata — it must not drift from the package version."""
    pyproject = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    pkg_version = pyproject["project"]["version"]

    server_json = json.loads(_SERVER_JSON.read_text(encoding="utf-8"))

    assert server_json["version"] == pkg_version, (
        f"server.json top-level version {server_json['version']!r} "
        f"does not match pyproject.toml {pkg_version!r}"
    )

    package = server_json["packages"][0]
    assert package["version"] == pkg_version, (
        f"server.json packages[0].version {package['version']!r} "
        f"does not match pyproject.toml {pkg_version!r}"
    )
