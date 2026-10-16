"""Immutable G intraday snapshots and an index for the arrow-based history viewer.
Only successful, quality-checked scans call this function. Missing sessions are
never synthesized or backfilled from later prices.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path

def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def archive_intraday_payload(data_dir, payload):
    """Return the immutable archive path after updating per-date and global indexes."""
    if payload.get("quality") != "intraday-provisional-allmarket" or not isinstance(payload.get("rows"), list):
        raise ValueError("Only successful full-market intraday G payloads may be archived")
    published = datetime.fromisoformat(payload["publishedAt"])
    day = published.strftime("%Y-%m-%d")
    if day != payload.get("asOfDate"):
        raise ValueError("Snapshot date must equal its actual publish date")
    base = Path(data_dir) / "g_intraday" / "archive"
    folder = base / day
    folder.mkdir(parents=True, exist_ok=True)
    stem = published.strftime("%H%M%S")
    filename = stem + ".json"
    sequence = 2
    while (folder / filename).exists():
        filename = f"{stem}-{sequence}.json"
        sequence += 1
    # Full payload, including rows, prices, scores and actual publication timestamp.
    _write_json(folder / filename, payload)
    manifest_file = folder / "index.json"
    manifest = _read_json(manifest_file, {"date": day, "snapshots": []})
    snapshots = manifest.get("snapshots", []) if manifest.get("date") == day else []
    if not isinstance(snapshots, list):
        snapshots = []
    snapshots.append({
        "file": filename,
        "publishedAt": payload["publishedAt"],
        "count": len(payload["rows"]),
        "coverage": payload.get("coverage", {}).get("valid"),
    })
    snapshots.sort(key=lambda item: (item["publishedAt"], item["file"]))
    _write_json(manifest_file, {"date": day, "snapshots": snapshots})
    # Global date catalog, sorted and available even after market close.
    days = sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "index.json").exists())
    _write_json(base / "index.json", {"dates": days})
    return folder / filename
