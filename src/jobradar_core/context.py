from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from jobradar_core.models import MemoryRecord, ResumeDocument

STABLE_PREFIX = """你是 JobRadar 的简历优化 Agent。

你的职责是基于候选人的真实简历证据，针对给定 JD 改善信息结构和表达。

必须遵守：
1. 不得编造候选人没有提供的职责、技能、数字、结果、公司或时间。
2. 每条修改必须返回 target_block_id、before、after、intent、evidence_refs 和 rationale。
3. before 必须逐字来自候选人简历；evidence_refs 必须引用提供的 source_ref。
4. JD 只表示雇主需求，不能当成候选人已经具备的经历。
5. 证据不足时 intent 使用 fact_needed，提出需要补充的事实，不直接写进简历。
6. 只返回 JSON，不返回 Markdown，不展示内部思维过程。

输出协议：
{
  "summary": "一句话诊断",
  "strengths": ["有证据的匹配点"],
  "gaps": ["缺口或待确认项"],
  "patches": [{
    "target_block_id": "b-0001",
    "before": "原文",
    "after": "建议文本",
    "intent": "wording|structure|fact_needed",
    "evidence_refs": ["resume:..."],
    "rationale": "为何这样调整"
  }]
}
"""


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CompiledContext:
    system: str
    user: str
    manifest: dict


class ContextCompiler:
    version = "resume_optimize@1"

    def compile(
        self,
        *,
        resume: ResumeDocument,
        jd_text: str,
        job_id: str = "",
        job_title: str = "",
        memories: list[MemoryRecord] | None = None,
    ) -> CompiledContext:
        memories = memories or []
        run_snapshot = {
            "resume_id": resume.resume_id,
            "resume_hash": resume.source_hash,
            "job_id": job_id,
            "job_title": job_title,
            "jd_hash": canonical_hash(jd_text),
            "workflow": self.version,
        }
        evidence = [
            {
                "block_id": block.block_id,
                "source_ref": block.source_ref,
                "text": block.text,
            }
            for block in resume.blocks[:240]
        ]
        memory_blocks = [
            {
                "memory_id": memory.memory_id,
                "level": memory.level,
                "summary": memory.summary,
                "source_ref": memory.source_ref,
            }
            for memory in memories[:30]
        ]
        dynamic = {
            "task": "diagnose_and_propose_grounded_resume_patches",
            "target_job": {"job_id": job_id, "title": job_title, "jd": jd_text[:30000]},
            "resume_evidence": evidence,
            "recalled_memory": memory_blocks,
        }
        user = json.dumps(dynamic, ensure_ascii=False, sort_keys=True)
        blocks = [
            {
                "type": "resume_evidence",
                "source_id": f"resume:{resume.resume_id}",
                "items": len(evidence),
                "estimated_tokens": _estimate_tokens(json.dumps(evidence, ensure_ascii=False)),
            },
            {
                "type": "jd",
                "source_id": f"job:{job_id or 'pasted'}",
                "items": 1,
                "estimated_tokens": _estimate_tokens(jd_text),
            },
        ]
        if memory_blocks:
            blocks.append(
                {
                    "type": "memory",
                    "source_id": "memory:resume",
                    "items": len(memory_blocks),
                    "estimated_tokens": _estimate_tokens(
                        json.dumps(memory_blocks, ensure_ascii=False)
                    ),
                }
            )
        manifest = {
            "compiler_version": self.version,
            "stable_prefix_hash": canonical_hash(STABLE_PREFIX),
            "run_snapshot_hash": canonical_hash(run_snapshot),
            "purpose": "resume.patch",
            "blocks": blocks,
            "dropped": [],
        }
        return CompiledContext(system=STABLE_PREFIX, user=user, manifest=manifest)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2)
