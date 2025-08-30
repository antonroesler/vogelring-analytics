from __future__ import annotations

from pathlib import Path
import json
from typing import Any

STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _view_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", " ")).strip()
    return STORAGE_DIR / f"{safe}.json"


def save_view(view: dict[str, Any]) -> None:
    path = _view_path(view["name"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(view, f, ensure_ascii=False, indent=2)


def delete_view(name: str) -> None:
    path = _view_path(name)
    if path.exists():
        path.unlink()


def load_view(name: str) -> dict[str, Any] | None:
    path = _view_path(name)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_views() -> list[dict[str, Any]]:
    views: list[dict[str, Any]] = []
    for f in sorted(STORAGE_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                views.append(json.load(fh))
        except Exception:
            continue
    return views
