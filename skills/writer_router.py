"""Writer Router — distributes a confirmed topic to parallel Workers.

Phase 1: single Worker (wechat). Phase 3: 3 Workers (wechat + xiaohongshu + douyin).
Router reads the confirmed topic, spawns Workers as subprocesses,
then Aggregator merges results into a single meta file.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    PENDING_DIR,
    PROJECT_ROOT,
    QUEUE_DIR,
    REVIEW_DIR,
    STATUS_DIR,
    TMP_DIR,
)

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

# Phase 3: all 3 workers active. Phase 1: only wechat.
# Controlled by env var PARALLEL_WORKERS — "1" for single, "3" for all.
PARALLEL = os.getenv("PARALLEL_WORKERS", "1") == "3"

WORKER_CONFIGS = [
    {
        "type": "wechat",
        "script": "writer.py",
        "args": [],
        "enabled": True,
        "timeout": 600,  # 10 min
    },
    {
        "type": "xiaohongshu",
        "script": "writer_xhs.py",
        "args": [],
        "enabled": PARALLEL,
        "timeout": 600,
    },
    {
        "type": "douyin",
        "script": "writer_douyin.py",
        "args": [],
        "enabled": PARALLEL,
        "timeout": 300,  # 5 min (scripts are shorter)
    },
]


def _write_router_status(pct: int, detail: str, workers: Optional[dict] = None):
    """Write router-level aggregated status."""
    status = {
        "agent": "writer",
        "router": True,
        "progress_pct": pct,
        "detail": detail,
        "started_at": RUN_TIMESTAMP,
        "workers": workers or {},
    }
    path = STATUS_DIR / "writer-router.json"
    tmp = STATUS_DIR / ".writer-router.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)


def _find_topic(topic_id: Optional[str] = None) -> tuple[Optional[Path], Optional[dict]]:
    """Find a confirmed topic."""
    if topic_id:
        for f in PENDING_DIR.glob(f"topic_*{topic_id}*.json"):
            return f, json.loads(f.read_text())

    # Find latest confirmed topic (stored in queue/topics/ by dashboard scanner)
    topics_dir = QUEUE_DIR / "topics"
    confirmed_files = sorted(topics_dir.glob("*.confirmed"), key=os.path.getmtime, reverse=True)
    for cf in confirmed_files:
        topic_name = cf.stem.replace(".confirmed", "")
        for f in PENDING_DIR.glob(f"*{topic_name}*"):
            if f.exists():
                return f, json.loads(f.read_text())
        # Also try the raw topic name
        topic_path = PENDING_DIR / f"{topic_name}.json"
        if topic_path.exists():
            return topic_path, json.loads(topic_path.read_text())
    return None, None


async def _run_worker(config: dict, topic_path: Path, topic: dict) -> dict:
    """Run a single Writer worker as a subprocess. Returns result."""
    worker_type = config["type"]
    script_path = PROJECT_ROOT / "skills" / config["script"]

    if not script_path.exists():
        return {
            "type": worker_type,
            "status": "skipped",
            "detail": f"Script not found: {script_path}",
        }

    # Worker writes to a temp subdirectory to avoid file conflicts
    work_dir = TMP_DIR / f"{RUN_TIMESTAMP}-{worker_type}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Pass topic as JSON via temp file (avoid CLI encoding issues)
    topic_file = work_dir / "topic.json"
    topic_file.write_text(json.dumps(topic, ensure_ascii=False))

    cmd = [
        "python3", str(script_path),
        "--topic-file", str(topic_file),
        "--work-dir", str(work_dir),
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=PROJECT_ROOT,
            ),
            timeout=config["timeout"],
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            # Find the output files in work_dir
            meta_files = list(work_dir.glob("*.meta.json"))
            article_files = list(work_dir.glob("*.md"))
            return {
                "type": worker_type,
                "status": "completed",
                "detail": stdout.decode()[:200],
                "article": str(article_files[0]) if article_files else None,
                "meta": str(meta_files[0]) if meta_files else None,
            }
        else:
            return {
                "type": worker_type,
                "status": "failed",
                "detail": stderr.decode()[:300] or stdout.decode()[:300],
            }
    except asyncio.TimeoutError:
        return {
            "type": worker_type,
            "status": "timeout",
            "detail": f"Exceeded {config['timeout']}s timeout",
        }
    except Exception as e:
        return {
            "type": worker_type,
            "status": "error",
            "detail": str(e),
        }


async def _aggregate(results: list[dict], topic: dict):
    """Merge Worker results into REVIEW_DIR. Write aggregated index."""
    articles = []
    for r in results:
        if r["status"] == "completed" and r.get("article"):
            # Copy to review directory
            src = Path(r["article"])
            meta_src = Path(r["meta"]) if r.get("meta") else None
            dest_article = REVIEW_DIR / f"{RUN_TIMESTAMP}-{r['type']}.md"
            dest_meta = REVIEW_DIR / f"{RUN_TIMESTAMP}-{r['type']}.meta.json"

            if src.exists():
                dest_article.write_text(src.read_text(encoding="utf-8"))
            if meta_src and meta_src.exists():
                dest_meta.write_text(meta_src.read_text(encoding="utf-8"))

            articles.append({
                "type": r["type"],
                "article": str(dest_article),
                "meta": str(dest_meta),
            })

    # Write aggregated index
    aggregated = {
        "topic": topic.get("title", ""),
        "timestamp": RUN_TIMESTAMP,
        "worker_count": len(results),
        "articles": articles,
        "status": "completed" if articles else "failed",
    }
    agg_path = REVIEW_DIR / f"{RUN_TIMESTAMP}-aggregated.json"
    tmp = REVIEW_DIR / f".{RUN_TIMESTAMP}-aggregated.json.tmp"
    tmp.write_text(json.dumps(aggregated, ensure_ascii=False, indent=2))
    os.rename(tmp, agg_path)
    return aggregated


async def main():
    topic_id = sys.argv[1] if len(sys.argv) > 1 else None
    topic_path, topic = _find_topic(topic_id)

    if not topic or not topic_path:
        print("[router] No confirmed topic found")
        _write_router_status(0, "无选题", {"error": "no topic"})
        return

    print(f"[router] Routing topic: {topic.get('title', 'unknown')}")
    _write_router_status(10, f"分发选题: {topic['title'][:30]}")

    # Select enabled workers
    active_workers = [w for w in WORKER_CONFIGS if w["enabled"]]
    print(f"[router] Active workers: {[w['type'] for w in active_workers]}")

    # Run all workers concurrently
    _write_router_status(20, "并行写作中", {
        w["type"]: {"status": "running", "stage": 0, "progress_pct": 0}
        for w in active_workers
    })

    tasks = [_run_worker(w, topic_path, topic) for w in active_workers]
    results = await asyncio.gather(*tasks)

    # Aggregate results
    _write_router_status(80, "合并结果")
    aggregated = await _aggregate(results, topic)

    # Update status
    worker_status = {}
    for w, r in zip(active_workers, results):
        worker_status[w["type"]] = {
            "status": r["status"],
            "stage": 7 if r["status"] == "completed" else None,
            "progress_pct": 100 if r["status"] == "completed" else 0,
        }

    _write_router_status(100, f"完成: {aggregated['status']}", worker_status)
    print(f"[router] Done. Workers: {len(results)}, Articles: {len(aggregated['articles'])}")


if __name__ == "__main__":
    asyncio.run(main())
