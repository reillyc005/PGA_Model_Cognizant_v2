from __future__ import annotations
import os
import time
import requests
from typing import Any, Dict

from ..report.logging import load_yaml, log
from .cache import cache_read, cache_write

class DataGolfError(RuntimeError):
    pass

def _cfg() -> dict:
    return load_yaml("config/datagolf.yaml")

def _ttl(endpoint_key: str) -> int:
    # conservative defaults for pre-tournament
    # skill/decomps/approach: 6h; schedule: 24h
    if endpoint_key in {"schedule"}:
        return 24 * 3600
    return 6 * 3600

def _req(endpoint_key: str, params: dict | None = None, *, attempts: int = 3, timeout: int = 30) -> Dict[str, Any]:
    cfg = _cfg()
    base = str(cfg.get("base_url", "")).rstrip("/")
    eps = cfg.get("endpoints", {}) or {}
    if endpoint_key not in eps:
        raise DataGolfError(f"Unknown endpoint key: {endpoint_key}")
    endpoint = eps[endpoint_key]

    key = os.environ.get("DATAGOLF_API_KEY", "")
    if not key:
        raise DataGolfError("DATAGOLF_API_KEY not set")

    p = dict(cfg.get("defaults", {}) or {})
    if params:
        p.update(params)
    p["key"] = key

    # cache
    ttl = _ttl(endpoint_key)
    hit, payload = cache_read("datagolf", endpoint, p, ttl)
    if hit:
        log(f"DataGolf cache hit: {endpoint_key}")
        return payload

    url = f"{base}{endpoint}"
    headers = {"User-Agent": "pga-model-v2 (+local)"}

    last_err: str | None = None
    for i in range(1, attempts + 1):
        try:
            r = requests.get(url, params=p, headers=headers, timeout=timeout)
            if r.status_code != 200:
                snippet = (r.text or "")[:300]
                raise DataGolfError(f"{url} -> {r.status_code}: {snippet}")
            payload = r.json()
            cache_write("datagolf", endpoint, p, payload)
            log(f"DataGolf fetched: {endpoint_key}")
            return payload
        except DataGolfError:
            raise
        except Exception as e:
            last_err = str(e)
            if i == attempts:
                raise DataGolfError(last_err)
            time.sleep(0.75 * i)

    raise DataGolfError(last_err or "Unknown DataGolf request failure")

def fetch_schedule(tour: str = "pga", upcoming_only: bool = True) -> dict:
    return _req("schedule", {"tour": tour, "upcoming_only": "yes" if upcoming_only else "no"})

def fetch_skill_ratings(tour: str = "pga", display: str = "value") -> dict:
    return _req("skill_ratings", {"tour": tour, "display": display})

def fetch_player_decomp(tour: str = "pga") -> dict:
    return _req("player_decomp", {"tour": tour})

def fetch_approach_skill(tour: str = "pga", period: str = "l24") -> dict:
    return _req("approach_skill", {"tour": tour, "period": period})


def fetch_pre_tournament(event_id: int, tour: str = "pga") -> dict:
    return _req("pre_tournament", {"tour": tour, "event_id": int(event_id), "odds_format": "percent"})
