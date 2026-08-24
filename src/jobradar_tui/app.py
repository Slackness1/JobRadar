from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Resize
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from jobradar_core.models import JobSearchQuery, JobSearchResult, ResumeOptimization
from jobradar_core.resume import verify_patches
from jobradar_core.service import JobRadarLocal


class JobRadarApp(App[None]):
    TITLE = "JobRadar Local"
    SUB_TITLE = "Jobs and grounded resume optimization"
    CSS_PATH = "theme.tcss"
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+j", "show_jobs", "Jobs"),
        ("ctrl+r", "show_resume", "Resume"),
        ("ctrl+x", "cancel_current", "Cancel run"),
    ]

    def __init__(self, service: JobRadarLocal):
        super().__init__()
        self.service = service
        self.job_results: dict[str, JobSearchResult] = {}
        self.selected_job_id = ""
        self.optimization: ResumeOptimization | None = None
        self.selected_patch_id = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="jobs-pane", id="workspace-tabs"):
            with TabPane("Jobs", id="jobs-pane"):
                with Horizontal(classes="toolbar"):
                    yield Input(placeholder="Keywords, e.g. AI Agent backend", id="job-query")
                    yield Input(placeholder="Location", id="job-location", classes="compact-input")
                    yield Input(placeholder="Track", id="job-track", classes="compact-input")
                    yield Button("Search", id="job-search", variant="primary")
                with Horizontal(id="jobs-workspace"):
                    with Vertical(id="jobs-list-pane"):
                        yield DataTable(id="jobs-table", cursor_type="row", zebra_stripes=True)
                    with VerticalScroll(id="job-detail-pane"):
                        yield Markdown(
                            "Select a job to inspect its source, JD, and ranking evidence.",
                            id="job-detail",
                        )
                        with Horizontal(classes="action-row"):
                            yield Button("Favorite", id="job-favorite")
                            yield Button("Exclude", id="job-exclude", variant="warning")
                            yield Button("Use for resume", id="job-use-resume", variant="success")
            with TabPane("Resume", id="resume-pane"):
                with Horizontal(classes="toolbar"):
                    yield Input(
                        placeholder="简历路径：PDF / DOCX / MD / TXT",
                        id="resume-path",
                    )
                    yield Button("Parse", id="resume-parse")
                    yield Button("Optimize", id="resume-optimize", variant="primary")
                with Horizontal(id="resume-workspace"):
                    with Vertical(id="resume-input-pane"):
                        yield Label("Target JD", classes="section-label")
                        yield TextArea(id="resume-jd", language=None, show_line_numbers=False)
                        yield Markdown("尚未解析简历。", id="resume-source")
                    with VerticalScroll(id="resume-output-pane"):
                        yield Markdown(
                            "完成解析后，诊断和 patch 会显示在这里。",
                            id="resume-diagnosis",
                        )
                        yield DataTable(id="patch-table", cursor_type="row", zebra_stripes=True)
                        yield Markdown("选择一条 patch 查看 diff。", id="patch-detail")
                        yield TextArea(id="patch-editor", show_line_numbers=False)
                        with Horizontal(classes="action-row"):
                            yield Button("Apply edit", id="patch-apply-edit")
                            yield Button("Accept", id="patch-accept", variant="success")
                            yield Button("Reject", id="patch-reject", variant="error")
                            yield Button("Export", id="resume-export", variant="primary")
            with TabPane("Runs", id="runs-pane"):
                yield DataTable(id="runs-table", cursor_type="row", zebra_stripes=True)
            with TabPane("Settings", id="settings-pane"):
                yield Markdown(id="settings-content")
        yield Static("Ready", id="status-line")
        yield Footer()

    def on_mount(self) -> None:
        jobs_table = self.query_one("#jobs-table", DataTable)
        jobs_table.add_columns("Score", "Company", "Title", "Location", "Source")
        patch_table = self.query_one("#patch-table", DataTable)
        patch_table.add_columns("State", "Block", "Intent", "Reason")
        runs_table = self.query_one("#runs-table", DataTable)
        runs_table.add_columns("Status", "Workflow", "State", "Started", "Run ID")
        self._refresh_settings()
        self._refresh_runs()
        self._search_jobs()
        self._apply_responsive_layout(self.size.width)

    def on_resize(self, event: Resize) -> None:
        self._apply_responsive_layout(event.size.width)

    def _apply_responsive_layout(self, width: int) -> None:
        self.screen.set_class(width < 90, "narrow")

    def action_show_jobs(self) -> None:
        self.query_one("#workspace-tabs", TabbedContent).active = "jobs-pane"

    def action_show_resume(self) -> None:
        self.query_one("#workspace-tabs", TabbedContent).active = "resume-pane"

    def action_cancel_current(self) -> None:
        cancelled = self.workers.cancel_group(self, "resume-optimize")
        if cancelled:
            self._set_status("Current resume run cancelled")
            self.notify("已取消当前简历任务")

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "job-search":
            self._search_jobs()
        elif button_id == "job-favorite":
            self._toggle_favorite()
        elif button_id == "job-exclude":
            self._toggle_excluded()
        elif button_id == "job-use-resume":
            self._use_selected_job()
        elif button_id == "resume-parse":
            self._parse_resume()
        elif button_id == "resume-optimize":
            self._start_optimize()
        elif button_id == "patch-accept":
            self._set_patch_status("accepted")
        elif button_id == "patch-reject":
            self._set_patch_status("rejected")
        elif button_id == "patch-apply-edit":
            self._apply_patch_edit()
        elif button_id == "resume-export":
            self._export_resume()

    @on(Input.Submitted, "#job-query")
    def submit_search(self) -> None:
        self._search_jobs()

    @on(DataTable.RowSelected, "#jobs-table")
    def select_job(self, event: DataTable.RowSelected) -> None:
        self.selected_job_id = str(event.row_key.value)
        self._render_job_detail()

    @on(DataTable.RowHighlighted, "#jobs-table")
    def highlight_job(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None:
            self.selected_job_id = str(event.row_key.value)
            self._render_job_detail()

    @on(DataTable.RowSelected, "#patch-table")
    def select_patch(self, event: DataTable.RowSelected) -> None:
        self.selected_patch_id = str(event.row_key.value)
        self._render_patch_detail()

    @on(DataTable.RowHighlighted, "#patch-table")
    def highlight_patch(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None:
            self.selected_patch_id = str(event.row_key.value)
            self._render_patch_detail()

    @on(TabbedContent.TabActivated)
    def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "runs-pane":
            self._refresh_runs()

    def _search_jobs(self) -> None:
        query = JobSearchQuery(
            text=self.query_one("#job-query", Input).value,
            location=self.query_one("#job-location", Input).value,
            track=self.query_one("#job-track", Input).value,
            limit=self.service.config.jobs.max_results,
        )
        self._set_status("Searching local job index...")
        results = self.service.search_jobs(query)
        self.job_results = {item.job.job_id: item for item in results}
        table = self.query_one("#jobs-table", DataTable)
        table.clear(columns=False)
        for item in results:
            table.add_row(
                f"{item.score:.2f}",
                item.job.company,
                item.job.title,
                item.job.location,
                item.job.source,
                key=item.job.job_id,
            )
        self.selected_job_id = results[0].job.job_id if results else ""
        self._render_job_detail()
        self._set_status(f"{len(results)} jobs · local deterministic ranking")

    def _render_job_detail(self) -> None:
        item = self.job_results.get(self.selected_job_id)
        detail = self.query_one("#job-detail", Markdown)
        if not item:
            detail.update("No matching jobs. Adjust the query or import another job file.")
            return
        job = item.job
        risks = "\n".join(f"- {risk}" for risk in item.risks) or "- No structured risks found"
        reasons = "\n".join(f"- {reason}" for reason in item.reasons)
        description = job.description or "No responsibilities provided"
        requirements = job.requirements or "No requirements provided"
        detail.update(
            f"""## {job.company} · {job.title}

`{job.location or "Location unknown"}` · `{job.track or "Track unspecified"}` · `{job.source}`

**Ranking relevance: {item.score:.2f}**, not a hiring probability.

### Why
{reasons}

### Risks
{risks}

### Responsibilities
{description}

### Requirements
{requirements}

### Source
{job.url or "No source link provided"}
"""
        )

    def _toggle_favorite(self) -> None:
        item = self.job_results.get(self.selected_job_id)
        if not item:
            self.notify("请先选择岗位", severity="warning")
            return
        value = not item.favorite
        self.service.jobs.set_favorite(item.job.job_id, value)
        self.job_results[item.job.job_id] = item.model_copy(update={"favorite": value})
        self.notify("已收藏" if value else "已取消收藏")

    def _toggle_excluded(self) -> None:
        item = self.job_results.get(self.selected_job_id)
        if not item:
            self.notify("请先选择岗位", severity="warning")
            return
        value = not item.excluded
        self.service.jobs.set_excluded(item.job.job_id, value, "TUI user decision")
        self.notify("已排除" if value else "已恢复")
        self._search_jobs()

    def _use_selected_job(self) -> None:
        item = self.job_results.get(self.selected_job_id)
        if not item:
            self.notify("请先选择岗位", severity="warning")
            return
        jd = "\n\n".join(
            part for part in (item.job.description, item.job.requirements) if part.strip()
        )
        self.query_one("#resume-jd", TextArea).load_text(jd)
        self.query_one("#workspace-tabs", TabbedContent).active = "resume-pane"
        self._set_status(f"Target job: {item.job.company} · {item.job.title}")

    def _parse_resume(self) -> None:
        value = self.query_one("#resume-path", Input).value.strip()
        if not value:
            self.notify("请输入简历文件路径", severity="warning")
            return
        try:
            document = self.service.resume_parser.parse(Path(value))
        except (OSError, ValueError) as exc:
            self.notify(str(exc), severity="error")
            return
        preview = "\n".join(f"- `{block.block_id}` {block.text}" for block in document.blocks[:20])
        self.query_one("#resume-source", Markdown).update(
            f"### Parsed evidence\n\n{len(document.blocks)} blocks · "
            f"`{document.source_hash[:12]}`\n\n{preview}"
        )
        self._set_status(f"Resume parsed: {len(document.blocks)} evidence blocks")

    def _start_optimize(self) -> None:
        value = self.query_one("#resume-path", Input).value.strip()
        if not value:
            self.notify("请输入简历文件路径", severity="warning")
            return
        jd_text = self.query_one("#resume-jd", TextArea).text.strip()
        if not jd_text and not self.selected_job_id:
            self.notify("请粘贴 JD 或从 Jobs 选择岗位", severity="warning")
            return
        self._optimize_resume(Path(value), jd_text, self.selected_job_id)

    @work(exclusive=True, group="resume-optimize", exit_on_error=False)
    async def _optimize_resume(self, resume_path: Path, jd_text: str, job_id: str) -> None:
        button = self.query_one("#resume-optimize", Button)
        button.disabled = True
        self._set_status("Compiling evidence and requesting model...")
        try:
            result = await self.service.optimize_resume(
                resume_path=resume_path, jd_text=jd_text, job_id=job_id
            )
        except Exception as exc:
            self.notify(str(exc), severity="error", timeout=8)
            self._set_status("Resume run failed")
        else:
            self.optimization = result
            self._render_optimization()
            self._set_status(
                f"Resume run {result.run_id[:8]} · {len(result.patches)} patches · {result.quality}"
            )
            if result.message:
                self.notify(result.message, severity="warning", timeout=8)
        finally:
            button.disabled = False
            self._refresh_runs()

    def _render_optimization(self) -> None:
        if not self.optimization:
            return
        diagnosis = self.optimization.diagnosis
        strengths = "\n".join(f"- {item}" for item in diagnosis.strengths) or "- 暂无"
        gaps = "\n".join(f"- {item}" for item in diagnosis.gaps) or "- 暂无"
        self.query_one("#resume-diagnosis", Markdown).update(
            f"""### Diagnosis

{diagnosis.summary}

**Matches**
{strengths}

**Gaps**
{gaps}
"""
        )
        table = self.query_one("#patch-table", DataTable)
        table.clear(columns=False)
        for patch in self.optimization.patches:
            table.add_row(
                patch.status,
                patch.target_block_id,
                patch.intent,
                patch.rationale[:60],
                key=patch.patch_id,
            )
        patch_ids = {patch.patch_id for patch in self.optimization.patches}
        if self.selected_patch_id not in patch_ids:
            self.selected_patch_id = (
                self.optimization.patches[0].patch_id if self.optimization.patches else ""
            )
        self._render_patch_detail()

    def _render_patch_detail(self) -> None:
        detail = self.query_one("#patch-detail", Markdown)
        patch = self._selected_patch()
        if not patch:
            detail.update("没有可显示的 patch。模型不可用时仍会保留本地诊断。")
            self.query_one("#patch-editor", TextArea).load_text("")
            return
        risks = "\n".join(f"- {item}" for item in patch.risk_flags) or "- 证据门未发现问题"
        evidence = "、".join(patch.evidence_refs) or "无"
        detail.update(
            f"""### Patch · {patch.status}

```diff
- {patch.before}
+ {patch.after}
```

**Rationale**  {patch.rationale or "未提供"}

**Evidence**  `{evidence}`

**Verification**
{risks}
"""
        )
        self.query_one("#patch-editor", TextArea).load_text(patch.after)

    def _selected_patch(self):
        if not self.optimization:
            return None
        return next(
            (
                patch
                for patch in self.optimization.patches
                if patch.patch_id == self.selected_patch_id
            ),
            None,
        )

    def _set_patch_status(self, status: str) -> None:
        if not self.optimization:
            self.notify("当前没有 patch", severity="warning")
            return
        selected = self._selected_patch()
        if not selected:
            self.notify("请先选择 patch", severity="warning")
            return
        if selected.status == "blocked" and status == "accepted":
            self.notify("这条修改未通过证据门，不能直接接受", severity="error")
            return
        patches = [
            patch.model_copy(update={"status": status})
            if patch.patch_id == self.selected_patch_id
            else patch
            for patch in self.optimization.patches
        ]
        self.optimization = self.optimization.model_copy(update={"patches": patches})
        self._render_optimization()

    def _apply_patch_edit(self) -> None:
        if not self.optimization:
            self.notify("当前没有 patch", severity="warning")
            return
        selected = self._selected_patch()
        if not selected:
            self.notify("请先选择 patch", severity="warning")
            return
        edited_text = self.query_one("#patch-editor", TextArea).text.strip()
        if not edited_text:
            self.notify("修改后的文本不能为空", severity="warning")
            return
        candidate = selected.model_copy(
            update={"after": edited_text, "risk_flags": [], "status": "edited"}
        )
        checked = verify_patches(
            [candidate], self.optimization.resume, self.optimization.diagnosis
        )[0]
        patches = [
            checked if patch.patch_id == selected.patch_id else patch
            for patch in self.optimization.patches
        ]
        self.optimization = self.optimization.model_copy(update={"patches": patches})
        self._render_optimization()
        if checked.status == "blocked":
            self.notify("编辑内容未通过证据门", severity="error")
        else:
            self.notify("编辑已保存，并重新通过证据检查")

    def _export_resume(self) -> None:
        if not self.optimization:
            self.notify("当前没有优化结果", severity="warning")
            return
        try:
            path = self.service.export_optimization(self.optimization)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self.notify(f"已导出 {path}", timeout=8)
        self._set_status(f"Exported: {path}")
        self._refresh_runs()

    def _refresh_runs(self) -> None:
        table = self.query_one("#runs-table", DataTable)
        table.clear(columns=False)
        for run in self.service.database.list_runs(100):
            table.add_row(
                run.status,
                run.workflow,
                run.state,
                run.created_at[:19],
                run.run_id[:12],
                key=run.run_id,
            )

    def _refresh_settings(self) -> None:
        config = self.service.config
        model = config.model
        if model.is_local:
            policy = "local"
        elif config.privacy.allow_remote_model:
            policy = "remote allowed"
        else:
            policy = "remote blocked"
        self.query_one("#settings-content", Markdown).update(
            f"""## Local configuration

| Item | Value |
| --- | --- |
| Data directory | `{self.service.workspace.root}` |
| Database | `{self.service.workspace.database_path}` |
| Jobs | {self.service.jobs.count()} |
| Model | `{model.model}` |
| Endpoint | `{model.base_url}` |
| Policy | {policy} |
| Telemetry | disabled |

API Key 只从环境变量 `{model.api_key_env}` 读取。修改配置后重新启动 TUI。
"""
        )

    def _set_status(self, text: str) -> None:
        self.query_one("#status-line", Static).update(text)
