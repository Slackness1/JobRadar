from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, TabbedContent, TextArea

from jobradar_core.service import JobRadarLocal
from jobradar_tui.app import JobRadarApp

from .conftest import FakeLLM


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(120, 40), (78, 32)])
async def test_tui_search_and_resume_vertical_slice(
    app_config, resume_file: Path, tmp_path: Path, size: tuple[int, int]
) -> None:
    service = JobRadarLocal(app_config, llm=FakeLLM())
    source = tmp_path / "jobs.jsonl"
    source.write_text(
        json.dumps(
            {
                "job_id": "job-agent-sh",
                "company": "测试科技",
                "job_title": "AI Agent 后端工程师",
                "location": "上海",
                "job_duty": "负责 Agent Runtime 和工具调用",
                "job_req": "Python、Redis、WebSocket",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service.job_importer.import_path(source)
    app = JobRadarApp(service)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.query_one("#jobs-table", DataTable).row_count == 1
        app.selected_job_id = "job-agent-sh"
        app._use_selected_job()
        assert app.query_one("#workspace-tabs", TabbedContent).active == "resume-pane"
        app.query_one("#resume-path", Input).value = str(resume_file)
        assert "WebSocket" in app.query_one("#resume-jd", TextArea).text
        app._start_optimize()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.optimization is not None
        assert app.query_one("#patch-table", DataTable).row_count == 1
        patch = app.optimization.patches[0]
        app.selected_patch_id = patch.patch_id
        app._render_patch_detail()
        editor = app.query_one("#patch-editor", TextArea)
        editor.load_text(f"{patch.before}\n负责 Agent 服务交付与复盘。")
        app._apply_patch_edit()
        assert app.optimization.patches[0].status == "edited"
        app._set_patch_status("accepted")
        assert app.optimization.patches[0].status == "accepted"
