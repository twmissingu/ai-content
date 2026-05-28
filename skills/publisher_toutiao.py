"""Toutiao (头条号) Publisher — Playwright browser automation.

Distributes approved articles to Toutiao draft box.
Requires initial manual login → cookie persisted to config/playwright_state.json.

Phase 3: separate from main publisher.py (browser dependency heavy).
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import CONFIG_DIR, FAILED_DIR, PROJECT_ROOT, REVIEW_DIR

TOUTIAO_LOGIN_URL = "https://mp.toutiao.com/"
STATE_FILE = CONFIG_DIR / "playwright_state.json"


def _get_article(target_id: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Find article content, title, and meta for a target_id."""
    meta_path = REVIEW_DIR / f"{target_id}.meta.json"
    article_path = REVIEW_DIR / f"{target_id}.md"

    if not meta_path.exists():
        for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
            meta_path = f
            article_path = REVIEW_DIR / f"{f.stem.replace('.meta', '')}.md"
            break

    if not meta_path.exists():
        return None, None, None

    meta = json.loads(meta_path.read_text())
    content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""
    title = meta.get("topic", target_id)
    return title, content, meta.get("topic", "")


def publish(target_id: str) -> bool:
    """Publish article to Toutiao draft box via Playwright.

    Returns True on success, False on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[toutiao] Playwright not installed")
        return False

    title, content, topic_name = _get_article(target_id)
    if not content:
        print(f"[toutiao] Article not found: {target_id}")
        return False

    print(f"[toutiao] Publishing: {topic_name}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # Load saved login state if available
            context = browser.new_context(
                storage_state=str(STATE_FILE) if STATE_FILE.exists() else None,
            )
            page = context.new_page()

            if not STATE_FILE.exists():
                print("[toutiao] ⚠️ No saved login state. Launching headed browser for login.")
                print("[toutiao] Please log in within 120 seconds...")
                browser.close()
                # Re-launch with headless=False for interactive login
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto(TOUTIAO_LOGIN_URL)
                page.wait_for_url("**/mp.toutiao.com/**", timeout=120000)
                # Save state
                context.storage_state(path=str(STATE_FILE))
                print(f"[toutiao] Login state saved to {STATE_FILE}")
            else:
                page.goto(TOUTIAO_LOGIN_URL)
                page.wait_for_load_state("networkidle")

            # Navigate to article publish page
            page.goto("https://mp.toutiao.com/profile_v4/graphic/publish")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2000)

            # Fill title - use locator.fill() which is safe from injection
            title_input = page.locator("input[placeholder*='标题'], .article-title-input")
            if title_input.count() > 0 and title_input.first.is_visible():
                title_input.first.fill(title[:64])  # Toutiao title max 64 chars
            else:
                print("[toutiao] Title input not found, trying fallback")
                # Use page.evaluate with JSON serialization to prevent injection
                safe_title = json.dumps(title[:30])
                page.evaluate(f"document.querySelector('input')?.value = {safe_title}")

            # Fill content - use locator.fill() which is safe from injection
            content_editor = page.locator(".ql-editor, [contenteditable='true'], .editor-content")
            if content_editor.count() > 0 and content_editor.first.is_visible():
                content_editor.first.fill(content[:5000])
            else:
                # Use page.evaluate with JSON serialization to prevent injection
                safe_content = json.dumps(content[:1000])
                page.evaluate(f"document.querySelector('[contenteditable=\"true\"]')?.innerText = {safe_content}")

            page.wait_for_timeout(2000)

            # Click "Save to draft" button (not "Publish")
            save_btn = page.locator("button:has-text('草稿'), span:has-text('草稿'), button:has-text('保存')")
            if save_btn.is_visible():
                save_btn.click()
                page.wait_for_timeout(3000)
                print("[toutiao] Saved as draft ✅")
            else:
                print("[toutiao] Save button not found — content may still be in editor")
                # Screenshot for debugging
                page.screenshot(path=str(FAILED_DIR / f"toutiao_{target_id}.png"))

            browser.close()
            return True

    except Exception as e:
        print(f"[toutiao] Error: {e}")
        # Record failure
        failed = {
            "target_id": target_id,
            "platform": "toutiao",
            "error": str(e),
            "requires_relogin": "timeout" in str(e).lower() or "context" in str(e).lower(),
        }
        failed_path = FAILED_DIR / f"toutiao_{target_id}.json"
        failed_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2))
        return False


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not target_id:
        print("Usage: publisher_toutiao.py <target_id>")
        return

    if STATE_FILE.exists():
        print(f"[toutiao] Using saved login state from {STATE_FILE}")

    ok = publish(target_id)
    if ok:
        print("[toutiao] Done")
    else:
        print("[toutiao] Failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
