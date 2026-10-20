import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class JsonlAudit:
    """Single-process JSONL sink. Use a managed append-only sink in production."""
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __call__(self, event: dict):
        record = {
            **event,
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            stream.flush()
