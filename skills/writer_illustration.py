"""Writer illustration — Agnes AI image generation with LLM prompt engineering.

Replaces the old HTML template + Playwright screenshot approach.
Stage 7 flow:
  1. Load style config from image_styles.json + illustration count from writing_styles.json
  2. LLM generates English image prompts based on article content
  3. Agnes API generates images from prompts

Note (#23): This is a helper module, not an agent. WriterAgent (which extends
AgentBase) passes its own logger to each function here, so this module does not
extend AgentBase directly.
"""

import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from config.settings import CONFIG_DIR
from skills.common import get_agent_logger


def _load_image_styles() -> dict:
    """Load image style mappings from config/image_styles.json."""
    path = CONFIG_DIR / "image_styles.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_illustration_count(worker_type: str) -> int:
    """Load illustration count from writing_styles.json for the given platform.

    Uses the platform default style (e.g., 'wechat_default').
    """
    path = CONFIG_DIR / "writing_styles.json"
    if not path.exists():
        return 3  # fallback
    try:
        styles = json.loads(path.read_text(encoding="utf-8"))
        default_key = f"{worker_type}_default"
        style = styles.get(default_key, {})
        return style.get("illustrations", 3)
    except (json.JSONDecodeError, OSError):
        return 3


def generate_image_prompts(
    text: str,
    topic_title: str,
    worker_type: str,
    content_type: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    image_styles: Optional[dict] = None,
) -> dict:
    """Use LLM to generate image prompts from article content.

    Returns: {"cover_prompt": str, "image_prompts": [str, ...]}
    """
    from skills.llm import LLMError, chat_structured
    from skills.common import load_prompt

    if logger is None:
        logger = get_agent_logger(__name__)

    if image_styles is None:
        image_styles = _load_image_styles()
    count = _load_illustration_count(worker_type)

    if count == 0:
        logger.info(f"illustrations=0 for {worker_type}, skipping image generation")
        return {"cover_prompt": "", "image_prompts": []}

    # Determine content type for style lookup
    if content_type is None:
        content_type = "tutorial"  # default fallback

    style_cfg = image_styles.get(content_type, image_styles.get("tutorial", {}))
    style_keywords = style_cfg.get("style", "modern, clean, high quality")
    aspect_ratio = style_cfg.get("aspect_ratio", "16:9")
    size = style_cfg.get("size", "1024x576")

    # image_count = total - 1 (cover)
    image_count = max(0, count - 1)

    # Load prompt template
    prompt_template = load_prompt(
        "image_prompt_gen",
        topic=topic_title,
        content_type=content_type,
        platform=worker_type,
        style=style_keywords,
        count=count,
        image_count=image_count,
        aspect_ratio=aspect_ratio,
        size=size,
        text_summary=text[:2000],
    )

    system_prompt = (
        "You are a professional AI image prompt engineer. "
        "Generate high-quality English image prompts based on article content. "
        "Always respond with valid JSON only."
    )

    try:
        result = chat_structured(
            system_prompt=system_prompt,
            user_prompt=prompt_template,
            json_mode=True,
            temperature=0.7,
        )
        cover_prompt = result.get("cover_prompt", "")
        image_prompts = result.get("image_prompts", [])

        logger.info(
            f"Generated {len(image_prompts) + 1} image prompts "
            f"(cover + {len(image_prompts)} inline)"
        )
        return {"cover_prompt": cover_prompt, "image_prompts": image_prompts}

    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Image prompt generation failed: {e}")
        return {"cover_prompt": "", "image_prompts": []}


def generate_images_agnes(
    prompts: list[str],
    img_dir: Path,
    size: str = "1024x576",
    logger: Optional[logging.Logger] = None,
) -> list[str]:
    """Generate images using Agnes API for a list of prompts.

    Returns list of local image file paths.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    agnes_script = Path(os.environ.get(
        "AGNES_SCRIPT_PATH",
        str(Path.home() / ".agents/skills/agnes-generate/scripts/image_gen.py"),
    ))
    if not agnes_script.exists():
        logger.error(f"Agnes script not found: {agnes_script}")
        return []

    def _sanitize_prompt(raw: str, max_len: int = 2000) -> str:
        """Strip control chars/null bytes and truncate LLM-generated prompt."""
        cleaned = raw.replace("\x00", "")
        cleaned = "".join(c for c in cleaned if c == "\n" or c == "\t" or (ord(c) >= 32))
        if len(cleaned) > max_len:
            logger.warning(
                f"Image prompt truncated from {len(cleaned)} to {max_len} chars"
            )
            cleaned = cleaned[:max_len]
        return cleaned

    def _generate_one(i: int, prompt: str) -> Optional[str]:
        output = img_dir / f"image_{i + 1}.png"
        safe_prompt = _sanitize_prompt(prompt)
        try:
            result = subprocess.run(
                ["python3", str(agnes_script), safe_prompt, str(output), size],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and output.exists():
                logger.info(f"Agnes generated: {output.name}")
                return str(output)
            else:
                logger.warning(
                    f"Agnes failed for image {i + 1}: {result.stderr[:200]}"
                )
        except subprocess.TimeoutExpired:
            logger.warning(f"Agnes timeout for image {i + 1}")
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning(f"Agnes error for image {i + 1}: {e}")
        return None

    tasks = [(i, p) for i, p in enumerate(prompts) if p]
    paths: list[str] = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(_generate_one, i, p): i for i, p in tasks
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                paths.append(result)

    return paths


def illustrate(
    text: str,
    topic_title: str,
    images_dir: Path,
    run_timestamp: str,
    domain: str,
    logger: Optional[logging.Logger] = None,
    worker_type: str = "wechat",
    content_type: Optional[str] = None,
) -> list[str]:
    """Full illustration pipeline: LLM prompts → Agnes image generation.

    Args:
        text: Article body text
        topic_title: Article title
        images_dir: Base images directory (config.settings.IMAGES_DIR)
        run_timestamp: Current run timestamp for directory naming
        domain: Domain tag (unused in Agnes mode, kept for compatibility)
        logger: Logger instance
        worker_type: Platform type (wechat/xiaohongshu/douyin)
        content_type: Content type (tutorial/news/etc.) for style lookup

    Returns: List of image file paths (PNG).
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    img_dir = images_dir / run_timestamp
    img_dir.mkdir(parents=True, exist_ok=True)

    # Load image styles once (shared between prompt generation and size lookup)
    image_styles = _load_image_styles()

    # Step 1: Generate prompts via LLM
    prompts_data = generate_image_prompts(
        text, topic_title, worker_type, content_type, logger,
        image_styles=image_styles,
    )

    all_prompts = []
    if prompts_data["cover_prompt"]:
        all_prompts.append(prompts_data["cover_prompt"])
    all_prompts.extend(prompts_data["image_prompts"])

    if not all_prompts:
        logger.info("No image prompts generated, skipping illustration")
        return []

    # Step 2: Determine image size from style config
    ct = content_type or "tutorial"
    style_cfg = image_styles.get(ct, image_styles.get("tutorial", {}))
    size = style_cfg.get("size", "1024x576")

    # Step 3: Generate images via Agnes
    paths = generate_images_agnes(all_prompts, img_dir, size, logger)

    logger.info(f"Illustration complete: {len(paths)} images generated")
    return paths
