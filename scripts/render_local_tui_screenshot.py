from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from textual.widgets import Input

from jobradar_core.config import default_config, save_config
from jobradar_core.models import JobRecord
from jobradar_core.service import JobRadarLocal
from jobradar_tui.app import JobRadarApp


async def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jobradar-screenshot-") as temp:
        root = Path(temp)
        os.environ["JOBRADAR_HOME"] = str(root / "data")
        os.environ["JOBRADAR_CONFIG_HOME"] = str(root / "config")
        config = default_config(root / "data")
        save_config(config)
        service = JobRadarLocal(config)
        service.jobs.upsert_many(
            [
                JobRecord(
                    job_id="demo-northstar-agent-backend",
                    company="Northstar Robotics (Demo)",
                    title="AI Agent Backend Engineer",
                    location="Shanghai",
                    track="Agent",
                    description=(
                        "Build an observable agent runtime, tool execution, and multimodal "
                        "conversation services for robotics products."
                    ),
                    requirements="Python, FastAPI, Redis, WebSocket, LLM integration",
                    source="offline_demo",
                    url="https://example.invalid/jobs/northstar-agent-backend",
                ),
                JobRecord(
                    job_id="demo-harbor-fde",
                    company="Harbor AI (Demo)",
                    title="Forward Deployed Engineer",
                    location="Shanghai",
                    track="Agent",
                    description=(
                        "Turn customer workflows into production agent solutions and own "
                        "delivery from discovery through evaluation."
                    ),
                    requirements="Python, solution design, evaluation, product sense",
                    source="offline_demo",
                    url="https://example.invalid/jobs/harbor-fde",
                ),
                JobRecord(
                    job_id="demo-lattice-platform",
                    company="Lattice Cloud (Demo)",
                    title="Backend Platform Engineer",
                    location="Hangzhou",
                    track="Backend",
                    description="Operate distributed APIs, queues, and deployment systems.",
                    requirements="Go, PostgreSQL, Kubernetes, observability",
                    source="offline_demo",
                    url="https://example.invalid/jobs/lattice-platform",
                ),
            ]
        )
        app = JobRadarApp(service)
        async with app.run_test(size=(140, 42)) as pilot:
            await pilot.pause()
            app.query_one("#job-query", Input).value = "AI Agent backend"
            app.query_one("#job-location", Input).value = "Shanghai"
            app.query_one("#job-track", Input).value = "Agent"
            app._search_jobs()
            await pilot.pause()
            screenshot = Path(app.save_screenshot("local-tui.svg", path=str(output_dir)))
            svg = "\n".join(
                line.rstrip() for line in screenshot.read_text(encoding="utf-8").splitlines()
            )
            screenshot.write_text(f"{svg}\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
