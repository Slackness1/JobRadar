import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / 'tmp' / 'screenshots'
SESSION_ID = os.environ.get('RESUME_COPILOT_SCREENSHOT_SESSION_ID', '15')
BASE_URL = os.environ.get(
    'RESUME_COPILOT_SCREENSHOT_URL',
    f'http://localhost:3001/resume-copilot?sessionId={SESSION_ID}',
)
DESIGN_VARIANTS = [
    value.strip()
    for value in os.environ.get('RESUME_COPILOT_SCREENSHOT_DESIGNS', 'default,apple,claude').split(',')
    if value.strip()
]


async def capture() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            for design in DESIGN_VARIANTS:
                design_query = '' if design == 'default' else f'&design={design}'
                url = BASE_URL if 'design=' in BASE_URL or design == 'default' else f'{BASE_URL}{design_query}'
                name_prefix = 'resume-copilot' if design == 'default' else f'resume-copilot-design-{design}'
                for name, should_expand_target in (
                    ('main', False),
                    ('target-expanded', True),
                ):
                    page = await browser.new_page(
                        viewport={'width': 1456, 'height': 1229},
                        device_scale_factor=1,
                    )
                    await page.goto(url, wait_until='networkidle')
                    await page.wait_for_timeout(1500)
                    if should_expand_target:
                        await page.get_by_role('button', name='修改目标岗位').click()
                        await page.wait_for_timeout(400)
                    output_path = OUTPUT_DIR / f'{name_prefix}-{name}.png'
                    await page.screenshot(path=str(output_path), full_page=False)
                    print(output_path)
                    await page.close()
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(capture())
