"""Writer illustration helpers — HTML template generation and screenshots.

Extracted from WriterAgent (Stage 7: illustrate) to keep writer.py focused
on the pipeline orchestration logic.
"""

import logging
from pathlib import Path
from typing import Optional


def generate_html_templates(
    text: str,
    topic_title: str,
    img_dir: Path,
    domain: str,
) -> list[Path]:
    """Generate HTML template files for illustrations.

    Takes the first 3 paragraphs longer than 50 chars and renders them
    as card-style HTML snippets suitable for screenshot conversion.
    """
    html_files: list[Path] = []
    paragraphs = [p for p in text.split("\n\n") if len(p) > 50]
    sections_to_illustrate = paragraphs[:3]

    for i, section in enumerate(sections_to_illustrate):
        section_title = section[:60].replace("\n", " ")
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>
body {{ font-family: -apple-system, sans-serif; background: #f8f9fa;
       display: flex; justify-content: center; align-items: center;
       min-height: 400px; margin: 0; padding: 20px; }}
.card {{ background: white; border-radius: 16px; padding: 32px;
        max-width: 580px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
.label {{ color: #666; font-size: 12px; letter-spacing: 0.5px;
         text-transform: uppercase; margin-bottom: 8px; }}
h2 {{ font-size: 20px; line-height: 1.5; color: #111; margin: 0 0 12px 0; }}
p {{ font-size: 15px; line-height: 1.7; color: #333; margin: 0; }}
.divider {{ height: 1px; background: #eee; margin: 16px 0; }}
.tag {{ display: inline-block; background: #e8f4fd; color: #1a73e8;
        padding: 4px 12px; border-radius: 20px; font-size: 12px; }}
</style></head><body>
<div class="card">
  <div class="label">稿定 · AI 观点</div>
  <h2>{topic_title}</h2>
  <div class="divider"></div>
  <p>{section_title[:200]}</p>
  <div class="divider"></div>
  <span class="tag">{domain}</span>
</div></body></html>"""
        html_path = img_dir / f"illustration_{i + 1}.html"
        html_path.write_text(html, encoding="utf-8")
        html_files.append(html_path)

    return html_files


def batch_screenshot(
    html_files: list[Path],
    logger: Optional[logging.Logger] = None,
) -> list[str]:
    """Batch screenshot HTML files, reusing a single browser instance.

    Falls back to returning the HTML paths when Playwright is not installed.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info("Playwright not installed, returning HTML files")
        return [str(f) for f in html_files]

    png_paths: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for html_path in html_files:
                try:
                    page = browser.new_page(
                        viewport={"width": 580, "height": 440},
                        device_scale_factor=2,
                    )
                    page.goto(f"file://{html_path.resolve()}")
                    page.wait_for_load_state("networkidle")
                    png_path = html_path.with_suffix(".png")
                    page.screenshot(path=str(png_path))
                    page.close()
                    png_paths.append(str(png_path))
                    logger.info(f"Screenshot: {png_path}")
                except Exception as e:
                    logger.warning(f"Screenshot failed for {html_path.name}: {e}")
                    png_paths.append(str(html_path))
            browser.close()
    except Exception as e:
        logger.error(f"Browser launch failed: {e}")
        return [str(f) for f in html_files]

    return png_paths


def illustrate(
    text: str,
    topic_title: str,
    images_dir: Path,
    run_timestamp: str,
    domain: str,
    logger: Optional[logging.Logger] = None,
) -> list[str]:
    """Full illustration pipeline: generate HTML templates then screenshot them."""
    if logger is None:
        logger = logging.getLogger(__name__)

    img_dir = images_dir / run_timestamp
    img_dir.mkdir(parents=True, exist_ok=True)

    html_files = generate_html_templates(text, topic_title, img_dir, domain)
    if not html_files:
        return []

    return batch_screenshot(html_files, logger)
