from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from jobradar_core.config import AppConfig, default_config, save_config


class WorkspaceBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def initialize(cls, config: AppConfig | None = None) -> Workspace:
        config = config or default_config()
        workspace = cls(config.data_dir.expanduser().resolve())
        for path in (
            workspace.root,
            workspace.original_resumes,
            workspace.resume_versions,
            workspace.job_imports,
            workspace.exports,
            workspace.runs,
            workspace.backups,
        ):
            path.mkdir(parents=True, exist_ok=True)
        save_config(config)
        return workspace

    @property
    def database_path(self) -> Path:
        return self.root / "jobradar.db"

    @property
    def original_resumes(self) -> Path:
        return self.root / "workspace" / "resumes" / "original"

    @property
    def resume_versions(self) -> Path:
        return self.root / "workspace" / "resumes" / "versions"

    @property
    def job_imports(self) -> Path:
        return self.root / "workspace" / "jobs" / "imports"

    @property
    def exports(self) -> Path:
        return self.root / "workspace" / "exports"

    @property
    def runs(self) -> Path:
        return self.root / "workspace" / "runs"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    def safe_path(self, relative: str | Path) -> Path:
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError(f"path escapes JobRadar workspace: {relative}") from exc
        return candidate

    def import_user_file(self, source: Path, destination_dir: Path) -> Path:
        source = source.expanduser().resolve(strict=True)
        digest = sha256_file(source)[:12]
        name = f"{source.stem}-{digest}{source.suffix.lower()}"
        destination = (destination_dir / name).resolve()
        try:
            destination.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceBoundaryError("destination is outside JobRadar workspace") from exc
        destination_dir.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        return destination


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
