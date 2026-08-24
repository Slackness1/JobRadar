from __future__ import annotations

import json
from pathlib import Path

import pytest

from jobradar_core.context import ContextCompiler
from jobradar_core.models import ResumePatch
from jobradar_core.resume import local_diagnosis, verify_patches
from jobradar_core.service import JobRadarLocal
from jobradar_core.workspace import sha256_file

from .conftest import FakeLLM


def test_resume_parse_context_and_memory_are_stable(app_config, resume_file: Path) -> None:
    service = JobRadarLocal(app_config, llm=FakeLLM())
    document = service.resume_parser.parse(resume_file)
    assert document.blocks
    assert Path(document.source_path).is_relative_to(service.workspace.root)
    memories = service.database.recall_memory(max_level="L3")
    assert any(memory.level == "L3" for memory in memories)

    compiler = ContextCompiler()
    first = compiler.compile(resume=document, jd_text="需要 Python 和 Agent")
    second = compiler.compile(resume=document, jd_text="需要 Python 和 Agent")
    assert first.manifest["stable_prefix_hash"] == second.manifest["stable_prefix_hash"]
    assert first.manifest["run_snapshot_hash"] == second.manifest["run_snapshot_hash"]


def test_verify_blocks_invented_number(app_config, resume_file: Path) -> None:
    service = JobRadarLocal(app_config, llm=FakeLLM())
    document = service.resume_parser.parse(resume_file)
    block = document.blocks[0]
    diagnosis = local_diagnosis(document.text, "需要 Python 和 Agent")
    patch = ResumePatch(
        patch_id="p1",
        target_block_id=block.block_id,
        before=block.text,
        after=f"{block.text}，性能提升 80%",
        evidence_refs=[block.source_ref],
    )
    verified = verify_patches([patch], document, diagnosis)
    assert verified[0].status == "blocked"
    assert any("数字" in risk for risk in verified[0].risk_flags)


def test_verify_requires_target_evidence_and_a_real_change(app_config, resume_file: Path) -> None:
    service = JobRadarLocal(app_config, llm=FakeLLM())
    document = service.resume_parser.parse(resume_file)
    first, second = document.blocks[:2]
    diagnosis = local_diagnosis(document.text, "需要 Python 和 Agent")
    wrong_evidence = ResumePatch(
        patch_id="p-wrong-evidence",
        target_block_id=first.block_id,
        before=first.text,
        after=f"负责交付：{first.text}",
        evidence_refs=[second.source_ref],
    )
    no_change = ResumePatch(
        patch_id="p-no-change",
        target_block_id=first.block_id,
        before=first.text,
        after=first.text,
        evidence_refs=[first.source_ref],
    )
    verified = verify_patches([wrong_evidence, no_change], document, diagnosis)
    assert all(patch.status == "blocked" for patch in verified)
    assert any("目标段落" in risk for risk in verified[0].risk_flags)
    assert any("没有变化" in risk for risk in verified[1].risk_flags)


@pytest.mark.asyncio
async def test_optimize_review_and_export_never_overwrite_original(
    app_config, resume_file: Path
) -> None:
    service = JobRadarLocal(app_config, llm=FakeLLM())
    original_hash = sha256_file(resume_file)
    result = await service.optimize_resume(
        resume_path=resume_file,
        jd_text="需要 Python、Agent、Redis 和 WebSocket",
    )
    assert result.patches[0].status == "proposed"
    run_manifest = service.workspace.runs / result.run_id / "manifest.json"
    artifact = run_manifest.read_text(encoding="utf-8")
    assert "周同学" not in artifact
    with service.database.connect() as connection:
        output_json = connection.execute(
            "SELECT output_json FROM runs WHERE run_id=?", (result.run_id,)
        ).fetchone()["output_json"]
    assert "周同学" not in output_json
    assert json.loads(output_json)["resume"]["source_hash"] == result.resume.source_hash
    accepted = [result.patches[0].model_copy(update={"status": "accepted"})]
    result = result.model_copy(update={"patches": accepted})
    exported = service.export_optimization(result)
    assert exported.exists()
    assert "负责交付" in exported.read_text(encoding="utf-8")
    assert "周同学" not in run_manifest.read_text(encoding="utf-8")
    assert sha256_file(resume_file) == original_hash
    assert sha256_file(Path(result.resume.source_path)) == original_hash


@pytest.mark.asyncio
async def test_missing_model_keeps_local_diagnosis(app_config, resume_file: Path) -> None:
    service = JobRadarLocal(app_config)
    result = await service.optimize_resume(
        resume_path=resume_file,
        jd_text="需要 Python、Agent 和 WebSocket",
    )
    assert result.quality == "degraded"
    assert result.diagnosis.matched_keywords
    assert result.patches == []
