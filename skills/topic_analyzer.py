"""Topic competition and saturation analysis.

Analyzes topic saturation by checking existing content in the knowledge base,
recent article history, and calculating competition metrics.
Helps Scout pick underserved topics with high potential.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from config.settings import KB_DIR


def extract_keywords(title: str) -> set[str]:
    """Extract significant keywords from a topic title."""
    # CJK + English word extraction
    words = set(re.findall(r'[\w一-鿿]{2,}', title.lower()))
    # Remove common stop words
    stop_words = {'的', '了', '在', '是', '和', '与', '或', '不', '有', '这', '那',
                  'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was'}
    return words - stop_words


def get_history_articles(days: int = 30) -> list[dict]:
    """Get recent articles from knowledge base history."""
    history_dir = KB_DIR / "history"
    articles = []
    if not history_dir.exists():
        return articles

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    for d in sorted(history_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        # Parse date from directory name
        try:
            dir_date = datetime.strptime(d.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if dir_date < cutoff:
                continue
        except ValueError:
            continue

        for f in d.glob("*.md"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            title = text.split("\n")[0].removeprefix("# ").strip()
            if title:
                articles.append({
                    "title": title,
                    "path": str(f),
                    "date": d.name,
                    "keywords": extract_keywords(title),
                })

    return articles


def _get_pending_topics() -> list[dict]:
    """Get topics currently in the pending queue."""
    from config.settings import PENDING_DIR
    topics = []
    if not PENDING_DIR.exists():
        return topics

    for f in PENDING_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            title = data.get("title", "")
            if title:
                topics.append({
                    "title": title,
                    "keywords": extract_keywords(title),
                })
        except (json.JSONDecodeError, OSError):
            pass

    return topics


def calculate_saturation(title: str, days: int = 30) -> dict:
    """Calculate topic saturation metrics.

    Returns dict with:
    - similar_count: Number of similar articles in history
    - recent_overlap: How many keywords overlap with recent articles
    - queue_overlap: How many keywords overlap with pending topics
    - saturation_score: 0-100 (0 = no competition, 100 = oversaturated)
    - similar_titles: List of similar article titles
    """
    keywords = extract_keywords(title)
    if not keywords:
        return {
            "similar_count": 0,
            "recent_overlap": 0,
            "queue_overlap": 0,
            "saturation_score": 0,
            "similar_titles": [],
        }

    # Check history
    history = get_history_articles(days)
    similar_count = 0
    similar_titles = []
    max_overlap_ratio = 0.0

    for article in history:
        article_kw = article["keywords"]
        if not article_kw:
            continue

        overlap = len(keywords & article_kw)
        overlap_ratio = overlap / max(len(keywords | article_kw), 1)

        if overlap_ratio > 0.3:  # 30% keyword overlap = similar
            similar_count += 1
            similar_titles.append(article["title"])

        max_overlap_ratio = max(max_overlap_ratio, overlap_ratio)

    # Check pending queue
    pending = _get_pending_topics()
    queue_overlap = 0
    for topic in pending:
        topic_kw = topic["keywords"]
        if not topic_kw:
            continue
        overlap = len(keywords & topic_kw)
        overlap_ratio = overlap / max(len(keywords | topic_kw), 1)
        if overlap_ratio > 0.3:
            queue_overlap += 1

    # Calculate saturation score
    # Factors:
    # - Number of similar articles (higher = more saturated)
    # - Recency of similar articles (more recent = more saturated)
    # - Queue overlap (more in queue = more saturated)
    history_factor = min(similar_count / 5.0, 1.0) * 40  # max 40 points
    overlap_factor = max_overlap_ratio * 30  # max 30 points
    queue_factor = min(queue_overlap / 3.0, 1.0) * 30  # max 30 points

    saturation_score = int(history_factor + overlap_factor + queue_factor)

    return {
        "similar_count": similar_count,
        "recent_overlap": round(max_overlap_ratio * 100, 1),
        "queue_overlap": queue_overlap,
        "saturation_score": min(saturation_score, 100),
        "similar_titles": similar_titles[:5],
    }


def analyze_topic_competition(title: str, source: str = "unknown") -> dict:
    """Full topic competition analysis.

    Returns dict with:
    - saturation: Saturation metrics from calculate_saturation()
    - source_diversity: Whether this source is already well-represented
    - recommendation: 'proceed' | 'caution' | 'skip'
    - reason: Explanation of recommendation
    """
    saturation = calculate_saturation(title)

    # Source diversity check
    history = get_history_articles(7)
    source_count = sum(1 for a in history if source in a.get("path", ""))
    source_overrepresented = source_count > 3

    # Recommendation logic
    score = saturation["saturation_score"]
    if score < 30:
        recommendation = "proceed"
        reason = "低竞争度，选题空间充足"
    elif score < 60:
        recommendation = "caution"
        reason = f"中等竞争度（相似文章 {saturation['similar_count']} 篇），建议差异化角度"
    else:
        recommendation = "skip"
        reason = f"高竞争度（相似文章 {saturation['similar_count']} 篇，队列中 {saturation['queue_overlap']} 个），建议换题"

    if source_overrepresented:
        reason += f"；来源 {source} 近期已过多"

    return {
        "saturation": saturation,
        "source_diversity": {
            "source": source,
            "recent_count": source_count,
            "overrepresented": source_overrepresented,
        },
        "recommendation": recommendation,
        "reason": reason,
    }
