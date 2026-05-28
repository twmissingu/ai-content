"""HTML → PNG screenshot pipeline for article illustrations.

Converts HTML templates to PNG images using Playwright.
Called by Writer Stage 7 (illustrate) to generate actual image files.
"""

import sys
from pathlib import Path
from typing import Optional

from config.settings import IMAGES_DIR


def html_to_png(html_path: Path, output_path: Optional[Path] = None, width: int = 580, height: int = 440) -> Optional[Path]:
    """Render an HTML file to PNG screenshot.

    Uses Playwright headless Chromium. Returns the output PNG path.
    Returns None on failure (graceful degrade — caller should fallback).
    """
    if output_path is None:
        output_path = html_path.with_suffix(".png")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[screenshot] Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=2,  # Retina quality
            )
            page.goto(f"file://{html_path.resolve()}")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        print(f"[screenshot] OK: {output_path}")
        return output_path
    except Exception as e:
        print(f"[screenshot] Failed: {e}")
        return None


def batch_convert(html_dir: Path) -> list[str]:
    """Convert all .html files in a directory to .png.

    Returns list of generated PNG paths.
    """
    pngs: list[str] = []
    for html_file in sorted(html_dir.glob("*.html")):
        png_path = html_file.with_suffix(".png")
        result = html_to_png(html_file, png_path)
        if result:
            pngs.append(str(result))
    return pngs


def main():
    """CLI entry: screenshot.py <html_path> [output_path]"""
    if len(sys.argv) < 2:
        print("Usage: screenshot.py <html_path> [output_png_path]")
        return

    html_path = Path(sys.argv[1])
    if not html_path.exists():
        print(f"File not found: {html_path}")
        return

    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    result = html_to_png(html_path, output_path)
    if result:
        print(str(result))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
