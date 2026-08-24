from __future__ import annotations

import asyncio
import json
import sqlite3
from importlib.resources import as_file, files
from pathlib import Path
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from jobradar_core import __version__
from jobradar_core.config import default_config, load_config, save_config
from jobradar_core.jobs import JobSearchQuery
from jobradar_core.models import ResumeOptimization
from jobradar_core.service import JobRadarLocal
from jobradar_core.workspace import Workspace

console = Console()
app = typer.Typer(
    name="jobradar",
    help="本地优先的岗位检索与证据化简历优化。",
    no_args_is_help=True,
)
jobs_app = typer.Typer(help="导入和检索本地岗位。")
resume_app = typer.Typer(help="解析和优化简历。")
config_app = typer.Typer(help="查看和修改本地模型配置。")
app.add_typer(jobs_app, name="jobs")
app.add_typer(resume_app, name="resume")
app.add_typer(config_app, name="config")


def _service() -> JobRadarLocal:
    return JobRadarLocal(load_config())


@app.command("version")
def version() -> None:
    """显示本地产品版本。"""
    console.print(f"JobRadar Local {__version__}")


@app.command("init")
def initialize(
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="用户数据目录；默认使用 XDG data 目录。"),
    ] = None,
    sample: Annotated[
        bool,
        typer.Option("--sample/--no-sample", help="导入离线演示岗位。"),
    ] = True,
) -> None:
    """创建本地工作区和配置，并可选导入演示岗位。"""
    config = default_config(data_dir)
    save_config(config)
    workspace = Workspace.initialize(config)
    service = JobRadarLocal(config)
    imported = 0
    if sample and service.jobs.count() == 0:
        resource = files("jobradar_core.resources").joinpath("jobs.sample.jsonl")
        with as_file(resource) as sample_path:
            imported = service.job_importer.import_path(sample_path).imported
    console.print("[bold green]JobRadar Local 已初始化[/bold green]")
    console.print(f"配置：{config.config_path}")
    console.print(f"数据：{workspace.root}")
    console.print(f"岗位：{service.jobs.count()} 条（本次导入 {imported} 条演示数据）")
    console.print("下一步：运行 [bold]jobradar doctor[/bold]，然后运行 [bold]jobradar tui[/bold]")


@app.command("doctor")
def doctor(
    check_model: Annotated[
        bool,
        typer.Option("--check-model", help="实际请求模型 endpoint 的 /models。"),
    ] = False,
) -> None:
    """检查工作区、SQLite、FTS5、模型授权和可选连通性。"""
    config = load_config()
    checks: list[tuple[str, bool, str]] = []
    try:
        workspace = Workspace.initialize(config)
        checks.append(("workspace", True, str(workspace.root)))
    except OSError as exc:
        checks.append(("workspace", False, str(exc)))
        workspace = None
    service = None
    if workspace:
        try:
            service = JobRadarLocal(config)
            with service.database.connect() as connection:
                connection.execute("SELECT rowid FROM jobs_fts LIMIT 1").fetchall()
            checks.append(("sqlite_fts5", True, f"schema ready · {service.jobs.count()} jobs"))
        except (sqlite3.DatabaseError, RuntimeError) as exc:
            checks.append(("sqlite_fts5", False, str(exc)))
    model = config.model
    model_allowed = model.is_local or config.privacy.allow_remote_model
    checks.append(
        (
            "model_policy",
            model_allowed,
            "local endpoint"
            if model.is_local
            else "remote endpoint allowed"
            if model_allowed
            else "remote endpoint blocked until privacy.allow_remote_model=true",
        )
    )
    if check_model and model_allowed:
        try:
            headers = {"Authorization": f"Bearer {model.api_key}"} if model.api_key else {}
            with httpx.Client(
                timeout=min(model.timeout_seconds, 15),
                trust_env=not model.is_local,
            ) as client:
                response = client.get(
                    f"{model.base_url.rstrip('/')}/models",
                    headers=headers,
                )
            response.raise_for_status()
            checks.append(("model_endpoint", True, f"HTTP {response.status_code}"))
        except httpx.HTTPError as exc:
            checks.append(("model_endpoint", False, str(exc)))
    table = Table(title="JobRadar Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in checks:
        table.add_row(name, "PASS" if ok else "FAIL", detail)
    console.print(table)
    if any(not ok for _, ok, _ in checks):
        raise typer.Exit(code=1)


@app.command("tui")
def launch_tui() -> None:
    """启动岗位与简历工作台。"""
    from jobradar_tui.app import JobRadarApp

    JobRadarApp(_service()).run()


@config_app.command("show")
def show_config() -> None:
    """显示配置，不输出 API Key。"""
    config = load_config()
    payload = config.model_dump(mode="json")
    payload["data_dir"] = str(config.data_dir)
    console.print_json(json.dumps(payload, ensure_ascii=False))


@config_app.command("model")
def configure_model(
    base_url: Annotated[str, typer.Option("--base-url")] = "http://127.0.0.1:11434/v1",
    model: Annotated[str, typer.Option("--model")] = "qwen3:8b",
    api_key_env: Annotated[str, typer.Option("--api-key-env")] = "JOBRADAR_LLM_API_KEY",
    allow_remote: Annotated[
        bool,
        typer.Option(
            "--allow-remote/--local-only",
            help="明确允许把简历/JD 发送到非本机 endpoint。",
        ),
    ] = False,
) -> None:
    """配置 OpenAI-compatible 或 Ollama endpoint；不会保存 API Key。"""
    config = load_config()
    updated = config.model_copy(
        update={
            "model": config.model.model_copy(
                update={
                    "base_url": base_url.rstrip("/"),
                    "model": model,
                    "api_key_env": api_key_env,
                }
            ),
            "privacy": config.privacy.model_copy(update={"allow_remote_model": allow_remote}),
        }
    )
    save_config(updated)
    endpoint_type = "local" if updated.model.is_local else "remote"
    console.print(f"已配置 {endpoint_type} model endpoint：{updated.model.base_url}")
    if not updated.model.is_local and not allow_remote:
        console.print("[yellow]远程 endpoint 仍被隐私策略阻止；请显式传 --allow-remote。[/yellow]")
    console.print(f"API Key 环境变量：{api_key_env}（Key 本身没有写入配置）")


@jobs_app.command("import")
def import_jobs(path: Path) -> None:
    """导入 CSV、JSON、JSONL 或 JobRadar SQLite 岗位文件。"""
    result = _service().job_importer.import_path(path)
    if result.errors:
        for error in result.errors:
            console.print(f"[yellow]{error}[/yellow]")
    console.print(
        f"导入完成：{result.imported} 条，跳过 {result.skipped} 条；"
        f"原始文件保存在 {result.source_path}"
    )
    if result.imported == 0 and result.errors:
        raise typer.Exit(code=1)


@jobs_app.command("search")
def search_jobs(
    query: Annotated[
        str,
        typer.Argument(help="自然语言关键词；可留空，只使用筛选条件。"),
    ] = "",
    location: str = "",
    company: str = "",
    track: str = "",
    limit: int = 20,
) -> None:
    """从本地岗位库检索并显示可解释排序。"""
    results = _service().search_jobs(
        JobSearchQuery(
            text=query,
            location=location,
            company=company,
            track=track,
            limit=limit,
        )
    )
    table = Table(title=f"岗位检索 · {len(results)} 条")
    table.add_column("Score", justify="right")
    table.add_column("Company")
    table.add_column("Title")
    table.add_column("Location")
    table.add_column("Job ID")
    table.add_column("Why")
    for item in results:
        table.add_row(
            f"{item.score:.2f}",
            item.job.company,
            item.job.title,
            item.job.location,
            item.job.job_id,
            "；".join(item.reasons[:2]),
        )
    console.print(table)


@resume_app.command("parse")
def parse_resume(path: Path) -> None:
    """将简历解析为可引用证据块。"""
    document = _service().resume_parser.parse(path)
    console.print(f"resume_id: {document.resume_id}")
    console.print(f"source_hash: {document.source_hash}")
    console.print(f"evidence_blocks: {len(document.blocks)}")
    for block in document.blocks[:10]:
        console.print(f"[{block.block_id}] {block.text}")


@resume_app.command("optimize")
def optimize_resume(
    resume_path: Path,
    jd_file: Annotated[Path | None, typer.Option("--jd-file")] = None,
    job_id: Annotated[str, typer.Option("--job-id")] = "",
    json_output: Annotated[bool, typer.Option("--json")] = False,
    accept_all: Annotated[
        bool,
        typer.Option("--accept-all", help="显式接受全部未被证据门阻断的 patch 并导出。"),
    ] = False,
) -> None:
    """针对目标 JD 诊断简历并生成可审阅 patch。"""
    jd_text = jd_file.read_text(encoding="utf-8") if jd_file else ""
    service = _service()
    result = asyncio.run(
        service.optimize_resume(resume_path=resume_path, jd_text=jd_text, job_id=job_id)
    )
    if json_output:
        console.print_json(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    else:
        _print_optimization(result)
    if accept_all:
        patches = [
            patch.model_copy(update={"status": "accepted"}) if patch.status == "proposed" else patch
            for patch in result.patches
        ]
        result = result.model_copy(update={"patches": patches})
        destination = service.export_optimization(result)
        console.print(f"[green]已导出：{destination}[/green]")


def _print_optimization(result: ResumeOptimization) -> None:
    console.print(f"[bold]{result.diagnosis.summary}[/bold]")
    if result.message:
        console.print(f"[yellow]{result.message}[/yellow]")
    for item in result.diagnosis.strengths:
        console.print(f"MATCH  {item}")
    for item in result.diagnosis.gaps:
        console.print(f"GAP    {item}")
    for patch in result.patches:
        console.print(f"\n[{patch.status}] {patch.target_block_id} · {patch.rationale}")
        console.print(f"- {patch.before}")
        console.print(f"+ {patch.after}")
        if patch.risk_flags:
            console.print(f"  risks: {'；'.join(patch.risk_flags)}")
