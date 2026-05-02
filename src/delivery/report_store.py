"""
Report Store — Busiv
=====================
Persists generated briefings to a JSON lines file.
The dashboard reads from this store to display history.

Why JSON lines not a database:
- Zero infrastructure — single file, no server
- Portable — travels with the deployment
- Readable — you can inspect it directly
- Fast enough for daily briefings (one write per day)
"""

import json
import uuid
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
STORE_PATH = Path("data/briefings.jsonl")
STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def save_briefing(briefing: dict) -> str:
    """
    Save a briefing to the store.
    Returns the report_id.
    """
    report_id = str(uuid.uuid4())[:8]
    briefing["report_id"] = report_id
    briefing["saved_at"] = datetime.utcnow().isoformat()

    try:
        with open(STORE_PATH, "a") as f:
            f.write(json.dumps(briefing) + "\n")
        logger.info(f"Briefing saved — ID: {report_id}")
    except Exception as e:
        logger.error(f"Failed to save briefing: {e}")

    return report_id


def load_briefings(limit: int = 30) -> list[dict]:
    """Load recent briefings from the store, newest first."""
    if not STORE_PATH.exists():
        return []
    try:
        with open(STORE_PATH) as f:
            lines = [l.strip() for l in f if l.strip()]
        briefings = [json.loads(l) for l in lines[-limit:]]
        return list(reversed(briefings))
    except Exception as e:
        logger.error(f"Failed to load briefings: {e}")
        return []


def load_latest_briefing() -> dict | None:
    """Load the most recently generated briefing."""
    briefings = load_briefings(limit=1)
    return briefings[0] if briefings else None


def load_briefing_by_id(report_id: str) -> dict | None:
    """Load a specific briefing by its ID."""
    if not STORE_PATH.exists():
        return None
    try:
        with open(STORE_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    b = json.loads(line)
                    if b.get("report_id") == report_id:
                        return b
    except Exception as e:
        logger.error(f"Failed to load briefing {report_id}: {e}")
    return None

