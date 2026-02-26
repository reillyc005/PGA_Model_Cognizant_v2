from __future__ import annotations
from pathlib import Path
import hashlib
import json
import time
from typing import Any

RAW_DIR = Path("data/raw")

def _key(source: str, endpoint: str, params: dict) -> str:
    # stable hash over sorted params
    items = "&".join(f"{k}={params[k]}" for k in sorted(params.keys()))
    base = f"{source}|{endpoint}|{items}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def cache_read(source: str, endpoint: str, params: dict, ttl_seconds: int, refresh: bool = False) -> tuple[bool, Any]:
    if refresh:
        return False, None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    k = _key(source, endpoint, params)
    fp = RAW_DIR / f"{source}_{k}.json"
    if not fp.exists():
        return False, None
    age = time.time() - fp.stat().st_mtime
    if age > ttl_seconds:
        return False, None
    with open(fp, "r", encoding="utf-8") as f:
        return True, json.load(f)

def cache_write(source: str, endpoint: str, params: dict, payload: Any) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    k = _key(source, endpoint, params)
    fp = RAW_DIR / f"{source}_{k}.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
