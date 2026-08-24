from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from jobradar_core.config import AppConfig
from jobradar_core.context import ContextCompiler, canonical_hash
from jobradar_core.database import LocalDatabase
from jobradar_core.jobs import JobImporter, JobRepository
from jobradar_core.llm import LLMError, LLMPort, OpenAICompatibleLLM
from jobradar_core.models import (
    JobSearchQuery,
    JobSearchResult,
    ResumeOptimization,
    ResumePatch,
)
from jobradar_core.resume import (
    ResumeParser,
    ResumeRepository,
    export_resume_version,
    local_diagnosis,
    verify_patches,
)
from jobradar_core.workspace import Workspace


class JobRadarLocal:
    def __init__(self, config: AppConfig, llm: LLMPort | None = None):
        self.config = config
        self.workspace = Workspace.initialize(config)
        self.database = LocalDatabase(self.workspace.database_path)
        self.jobs = JobRepository(self.database)
        self.job_importer = JobImporter(self.jobs, self.workspace)
        self.resumes = ResumeRepository(self.database)
        self.resume_parser = ResumeParser(self.workspace, self.resumes, self.database)
        self.context_compiler = ContextCompiler()
        self.llm = llm or OpenAICompatibleLLM(config)

    def search_jobs(self, query: JobSearchQuery) -> list[JobSearchResult]:
        started = time.perf_counter()
        run_id = self.database.create_run("job_search", canonical_hash(query.model_dump()))
        self.database.add_event(run_id, "normalize_query", "completed", summary=query.text)
        results = self.jobs.search(query)
        duration = int((time.perf_counter() - started) * 1000)
        self.database.add_event(
            run_id,
            "retrieve_and_rank",
            "completed",
            summary=f"返回 {len(results)} 个真实 job_id",
            duration_ms=duration,
        )
        output = {
            "query": query.model_dump(),
            "job_ids": [item.job.job_id for item in results],
        }
        self.database.update_run(run_id, state="complete", status="completed", output=output)
        self._write_run_artifacts(run_id, {"purpose": "job.search", **output})
        return results

    async def optimize_resume(
        self,
        *,
        resume_path: Path,
        jd_text: str,
        job_id: str = "",
    ) -> ResumeOptimization:
        run_id = self.database.create_run("resume_optimize")
        started = time.perf_counter()
        try:
            document = self.resume_parser.parse(resume_path)
            self.database.add_event(
                run_id,
                "parse_resume",
                "completed",
                summary=f"{len(document.blocks)} 个证据块",
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            job = self.jobs.get(job_id) if job_id else None
            if job and not jd_text.strip():
                jd_text = "\n".join(
                    part for part in (job.description, job.requirements) if part.strip()
                )
            if not jd_text.strip():
                raise ValueError("请粘贴目标 JD，或选择一个包含 JD 的本地岗位")
            diagnosis = local_diagnosis(document.text, jd_text)
            # L3 resume evidence is direct; memory recall only adds higher-level facts.
            memories = self.database.recall_memory(
                scopes=("global", "resume"), max_level="L2", limit=30
            )
            compiled = self.context_compiler.compile(
                resume=document,
                jd_text=jd_text,
                job_id=job_id,
                job_title=job.title if job else "",
                memories=memories,
            )
            snapshot_hash = compiled.manifest["run_snapshot_hash"]
            self.database.update_run(
                run_id,
                state="diagnose",
                snapshot_hash=snapshot_hash,
                manifest=compiled.manifest,
            )
            self.database.add_event(
                run_id,
                "compile_context",
                "completed",
                summary=f"Stable/Run/Turn context，{len(memories)} 条记忆索引",
            )

            patches: list[ResumePatch] = []
            quality = "valid"
            message = ""
            try:
                raw = await self.llm.complete_json(system=compiled.system, user=compiled.user)
                diagnosis = diagnosis.model_copy(
                    update={
                        "summary": str(raw.get("summary") or diagnosis.summary),
                        "strengths": _string_list(raw.get("strengths")) or diagnosis.strengths,
                        "gaps": _string_list(raw.get("gaps")) or diagnosis.gaps,
                    }
                )
                patches = _parse_patches(raw.get("patches"))
                self.database.add_event(
                    run_id,
                    "propose_patch",
                    "completed",
                    summary=f"模型返回 {len(patches)} 条 patch",
                )
            except LLMError as exc:
                quality = "degraded"
                message = str(exc)
                self.database.add_event(
                    run_id,
                    "propose_patch",
                    "degraded",
                    summary=message,
                    quality="degraded",
                    error_code="llm_unavailable",
                )
            verified = verify_patches(patches, document, diagnosis)
            blocked = sum(patch.status == "blocked" for patch in verified)
            self.database.add_event(
                run_id,
                "verify_patch",
                "completed",
                summary=f"{len(verified)} 条中 {blocked} 条被证据门阻断",
                quality="degraded" if blocked else "valid",
            )
            result = ResumeOptimization(
                run_id=run_id,
                resume=document,
                job_id=job_id,
                job_title=job.title if job else "",
                jd_hash=canonical_hash(jd_text),
                diagnosis=diagnosis,
                patches=verified,
                context_manifest=compiled.manifest,
                quality=quality,
                message=message,
            )
            run_output = _resume_run_output(result)
            self.database.update_run(
                run_id,
                state="user_review",
                status="completed",
                output=run_output,
            )
            self._write_run_artifacts(run_id, run_output)
            return result
        except Exception as exc:
            self.database.add_event(
                run_id,
                "workflow",
                "failed",
                summary=str(exc),
                quality="unavailable",
                error_code=type(exc).__name__,
            )
            self.database.update_run(run_id, state="failed", status="failed", error=str(exc))
            self._write_run_artifacts(run_id, {"error": str(exc)})
            raise

    def export_optimization(self, optimization: ResumeOptimization) -> Path:
        path = export_resume_version(
            document=optimization.resume,
            patches=optimization.patches,
            run_id=optimization.run_id,
            workspace=self.workspace,
            repository=self.resumes,
        )
        self.database.add_event(optimization.run_id, "export", "completed", summary=str(path))
        run_output = {**_resume_run_output(optimization), "export_path": str(path)}
        self.database.update_run(
            optimization.run_id,
            state="complete",
            status="completed",
            output=run_output,
        )
        self._write_run_artifacts(optimization.run_id, run_output)
        return path

    def _write_run_artifacts(self, run_id: str, output: dict) -> None:
        run_dir = self.workspace.runs / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        with self.database.connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            events = connection.execute(
                "SELECT * FROM run_events WHERE run_id=? ORDER BY occurred_at", (run_id,)
            ).fetchall()
        manifest = {
            "run_id": run_id,
            "workflow": run["workflow"],
            "state": run["state"],
            "status": run["status"],
            "snapshot_hash": run["snapshot_hash"],
            "context_manifest": json.loads(run["manifest_json"]),
            "output": output,
        }
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        event_lines = [json.dumps(dict(row), ensure_ascii=False) for row in events]
        (run_dir / "events.jsonl").write_text(
            "\n".join(event_lines) + ("\n" if event_lines else ""), encoding="utf-8"
        )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:12]


def _parse_patches(value: object) -> list[ResumePatch]:
    if not isinstance(value, list):
        return []
    patches: list[ResumePatch] = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        try:
            patches.append(
                ResumePatch(
                    patch_id=uuid.uuid4().hex,
                    target_block_id=str(item.get("target_block_id") or ""),
                    before=str(item.get("before") or ""),
                    after=str(item.get("after") or ""),
                    intent=str(item.get("intent") or "wording"),
                    evidence_refs=_string_list(item.get("evidence_refs")),
                    rationale=str(item.get("rationale") or ""),
                )
            )
        except ValueError:
            continue
    return patches


def _resume_run_output(result: ResumeOptimization) -> dict:
    """Keep the run trace useful without duplicating resume or prompt contents."""
    return {
        "run_id": result.run_id,
        "quality": result.quality,
        "resume": {
            "resume_id": result.resume.resume_id,
            "source_hash": result.resume.source_hash,
            "evidence_blocks": len(result.resume.blocks),
        },
        "target": {
            "job_id": result.job_id,
            "job_title": result.job_title,
            "jd_hash": result.jd_hash,
        },
        "diagnosis": {
            "matched_keywords": result.diagnosis.matched_keywords,
            "missing_keywords": result.diagnosis.missing_keywords,
        },
        "patches": [
            {
                "patch_id": patch.patch_id,
                "target_block_id": patch.target_block_id,
                "intent": patch.intent,
                "status": patch.status,
                "evidence_refs": patch.evidence_refs,
                "risk_flags": patch.risk_flags,
            }
            for patch in result.patches
        ],
        "context_manifest": result.context_manifest,
    }
