from __future__ import annotations

from pathlib import Path

import pytest

from jobradar_core.config import ModelConfig
from jobradar_core.workspace import Workspace, WorkspaceBoundaryError, sha256_file


def test_workspace_blocks_path_escape(app_config) -> None:
    workspace = Workspace.initialize(app_config)
    with pytest.raises(WorkspaceBoundaryError):
        workspace.safe_path("../../outside.txt")


def test_imported_original_is_content_addressed_and_unchanged(app_config, tmp_path: Path) -> None:
    workspace = Workspace.initialize(app_config)
    source = tmp_path / "resume.md"
    source.write_text("original fact", encoding="utf-8")
    before = sha256_file(source)
    imported = workspace.import_user_file(source, workspace.original_resumes)
    assert imported.exists()
    assert sha256_file(imported) == before
    source.write_text("changed outside workspace", encoding="utf-8")
    assert sha256_file(imported) == before


def test_docker_host_model_is_treated_as_local() -> None:
    model = ModelConfig(base_url="http://host.docker.internal:11434/v1")
    assert model.is_local is True
