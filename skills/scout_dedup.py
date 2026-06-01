"""Scout dedup — topic deduplication and filtering.

Three-layer dedup:
  1. Title overlap (word + character level) for CJK/English mixed text
  2. Entity/keyword overlap for cross-source event dedup
  3. Recent history check to skip topics covered in last N days
"""

import json
import re
from pathlib import Path
from typing import Optional

from config.settings import KB_DIR, PENDING_DIR
from skills.common import get_agent_logger

logger = get_agent_logger("scout")

# ── Constants ──────────────────────────────────────────────────────
SAME_TOPIC_BLOCK_DAYS = 3
HISTORY_DIR = KB_DIR / "history"


# ── Dedup & Filter ─────────────────────────────────────────────────
def _is_same_topic(title_a: str, title_b: str) -> bool:
    """Simple title-level dedup: check significant word overlap.

    Uses both word-level and character-level matching for better CJK support.
    """
    # Word-level matching (for mixed Chinese/English)
    words_a = set(re.findall(r'[\w一-鿿]{2,}', title_a.lower()))
    words_b = set(re.findall(r'[\w一-鿿]{2,}', title_b.lower()))

    if words_a and words_b:
        word_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
        if word_overlap > 0.5:
            return True

    # Character-level matching (better for Chinese)
    chars_a = set(re.findall(r'[一-鿿]', title_a))
    chars_b = set(re.findall(r'[一-鿿]', title_b))

    # Require significant character overlap (at least 3 chars in common)
    if chars_a and chars_b and len(chars_a & chars_b) >= 3:
        char_overlap = len(chars_a & chars_b) / max(len(chars_a | chars_b), 1)
        if char_overlap > 0.6:
            return True

    # Check if one title contains the other (require 50% containment)
    clean_a = re.sub(r'[^\w一-鿿]', '', title_a.lower())
    clean_b = re.sub(r'[^\w一-鿿]', '', title_b.lower())
    if len(clean_a) >= 4 and len(clean_b) >= 4:
        shorter = min(len(clean_a), len(clean_b))
        longer = max(len(clean_a), len(clean_b))
        if shorter / longer > 0.5:
            if clean_a in clean_b or clean_b in clean_a:
                return True

    return False


def _recent_topics(days: int = SAME_TOPIC_BLOCK_DAYS) -> set[str]:
    """Return set of topic titles written in the past N days."""
    recent = set()
    if HISTORY_DIR.exists():
        for d in list(HISTORY_DIR.iterdir()):
            if d.is_dir():
                for f in d.glob("*.md"):
                    try:
                        with open(f, encoding="utf-8", errors="ignore") as fh:
                            first_line = fh.readline(200)  # read only first 200 bytes
                        title = first_line.removeprefix("# ").strip()
                        if title:
                            recent.add(title)
                    except OSError:
                        pass
    # Also check pending
    for f in PENDING_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if data.get("title"):
                recent.add(data["title"])
        except (json.JSONDecodeError, OSError):
            pass
    return recent


def dedup_and_filter(candidates: list[dict]) -> list[dict]:
    """Remove duplicates and topics written recently.

    Uses three dedup layers:
      1. Title overlap (_is_same_topic) — word/char level matching
      2. Entity overlap (>=2 shared keywords) — cross-source event dedup
      3. Recent history check — skip topics covered in last 3 days
    """
    recent = _recent_topics()
    unique: list[dict] = []
    seen_title_sets: list[set[str]] = []  # track multiple titles per candidate
    seen_keyword_sets: list[set] = []

    for c in candidates:
        title = c["title"].strip()
        if not title or len(title) < 4:
            continue

        # Check recent topics (title-based)
        if any(_is_same_topic(title, rt) for rt in recent):
            continue

        # Check previously seen in this batch (title-based)
        if any(_is_same_topic(title, st) for st_set in seen_title_sets for st in st_set):
            continue

        # Check entity overlap for RSS vs hot-list dedup
        c_keywords = c.get("keywords", [])
        if c_keywords:
            c_keyword_set = {k.lower() for k in c_keywords}
            for i, seen_set in enumerate(seen_keyword_sets):
                shared = c_keyword_set & seen_set
                if len(shared) >= 2:
                    # Same event — keep the one with higher hot_value or RSS priority
                    existing = unique[i]
                    existing_hot = existing.get("hot_value", 0)
                    candidate_hot = c.get("hot_value", 0)
                    existing_is_rss = existing.get("source", "") == "rss"
                    candidate_is_rss = c.get("source", "") == "rss"

                    if candidate_is_rss and not existing_is_rss:
                        # RSS version is earlier — replace the hot-list version
                        unique[i] = c
                        seen_title_sets[i].add(title)  # keep both titles for dedup
                        seen_keyword_sets[i] = c_keyword_set
                    elif not candidate_is_rss and existing_is_rss:
                        # Keep the existing RSS version
                        pass
                    elif candidate_hot > existing_hot:
                        # Keep the higher hot_value version
                        unique[i] = c
                        seen_title_sets[i].add(title)  # keep both titles for dedup
                        seen_keyword_sets[i] = c_keyword_set
                    break
            else:
                # No entity overlap with any seen item
                seen_title_sets.append({title})
                seen_keyword_sets.append(c_keyword_set)
                unique.append(c)
        else:
            seen_title_sets.append({title})
            seen_keyword_sets.append(set())
            unique.append(c)

    return unique
