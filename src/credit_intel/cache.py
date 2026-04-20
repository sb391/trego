from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import CreditIntelConfig


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8")


def profile_cache_path(config: CreditIntelConfig, company_key: str) -> Path:
    return config.profiles_cache_dir / f"{company_key}.json"


def search_cache_path(config: CreditIntelConfig, cache_key: str) -> Path:
    return config.search_cache_dir / f"{cache_key}.json"
