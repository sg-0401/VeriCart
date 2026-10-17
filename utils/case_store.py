"""Small JSON-backed human-review queue for the demo application."""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
STORE = BASE / "data" / "cases.json"
STORE.parent.mkdir(parents=True, exist_ok=True)


def _load():
    if not STORE.exists(): return []
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    STORE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def create_case(payload):
    items = _load()
    case = {
        "case_id": "CASE-" + uuid.uuid4().hex[:8].upper(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "PENDING",
        **payload,
    }
    items.insert(0, case)
    _save(items)
    return case


def list_cases(status=None):
    items = _load()
    if status: items = [x for x in items if x.get("status") == status]
    return items


def get_case(case_id):
    return next((x for x in _load() if x.get("case_id") == case_id), None)


def update_case(case_id, status, note=""):
    items = _load()
    for item in items:
        if item.get("case_id") == case_id:
            item["status"] = status
            item["management_note"] = note
            item["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(items)
            return item
    return None
