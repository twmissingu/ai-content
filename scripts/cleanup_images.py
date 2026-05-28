#!/usr/bin/env python3
"""Clean up images older than 7 days from queue/images/.

Runs daily via system cron. Removes entire session directories
whose timestamp is > 7 days old.
"""

import sys
import time

from config.settings import IMAGES_DIR

MAX_AGE_SECONDS = 7 * 24 * 3600


def main():
    now = time.time()
    removed = 0
    for d in IMAGES_DIR.iterdir():
        if d.is_dir():
            age = now - d.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                # Remove directory and contents
                for f in d.iterdir():
                    f.unlink()
                d.rmdir()
                removed += 1
                print(f"[cleanup] Removed: {d.name}")

    print(f"[cleanup] Done. Removed {removed} directories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
