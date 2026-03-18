from __future__ import annotations

import os
import subprocess

from importlib.metadata import metadata


PROJECT_URL = os.environ.get("PROJECT_URL", "https://github.com/jakob1379/ruff-explain")


def test_smoke_can_run_cli_version() -> None:
    result = subprocess.run(
        ["ruff-explain", "--version"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.startswith("ruff-explain ")


def test_smoke_project_metadata_contains_repository_url() -> None:
    project_urls = metadata("ruff-explain").get_all("Project-URL")
    assert project_urls is not None
    assert any(PROJECT_URL in entry for entry in project_urls)
