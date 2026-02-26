from __future__ import annotations
from ..report.logging import log
from .datagolf_client import fetch_schedule, fetch_pre_tournament

def _extract_players(pret: dict) -> list[dict]:
    """Schema-tolerant extraction of player list from pre-tournament payload."""
    # Try common top-level keys (DataGolf uses 'baseline' for pre-tournament preds)
    for key in ("field", "players", "baseline", "baseline_history_fit", "data"):
        val = pret.get(key)
        if isinstance(val, list) and len(val) > 0:
            return val
        # Handle nested dict (e.g. {"data": {"players": [...]}})
        if isinstance(val, dict):
            for subkey in ("players", "field", "entries"):
                sub = val.get(subkey)
                if isinstance(sub, list) and len(sub) > 0:
                    return sub
    return []

def _parse_field(players: list[dict]) -> list[dict]:
    """Normalize player dicts into [{"Player": name}, ...]."""
    field = []
    for p in players:
        name = p.get("player_name") or p.get("name") or p.get("player") or ""
        if not name:
            continue
        field.append({"Player": name})
    return field

def resolve_event(tour: str = "pga", refresh: bool = False) -> dict:
    # choose next upcoming event from schedule then fetch pre-tournament to get field list
    sched = fetch_schedule(tour=tour, upcoming_only=True, refresh=refresh)
    events = sched.get("schedule") or sched.get("events") or sched.get("tournaments") or []
    if not events:
        raise RuntimeError("No upcoming events returned by DataGolf schedule endpoint")

    # pick first
    ev = events[0]
    event_id = ev.get("event_id") or ev.get("dg_event_id") or ev.get("id")
    if event_id is None:
        raise RuntimeError("Could not determine event_id from schedule payload")

    event_name = ev.get("event_name") or ev.get("name") or "Unknown Event"
    course = ev.get("course") or ev.get("venue") or ""
    date = ev.get("start_date") or ev.get("date") or ""

    log(f"Resolved event_id={event_id} ({event_name})")

    pret = fetch_pre_tournament(event_id=int(event_id), tour=tour, refresh=refresh)
    players = _extract_players(pret)
    field = _parse_field(players)

    # Auto-refresh guardrail: if field is empty and we haven't already refreshed, retry once
    if len(field) == 0 and not refresh:
        log("Field=0 from cache. Forcing refresh once...")
        return resolve_event(tour=tour, refresh=True)

    if len(field) == 0:
        raise RuntimeError(
            f"Pre-tournament endpoint returned 0 players for event_id={event_id} "
            f"({event_name}) even after forced refresh. "
            f"Response top-level keys: {list(pret.keys())}"
        )

    return {
        "event_id": int(event_id),
        "event_name": event_name,
        "course": course,
        "date": date,
        "players": field,
        "field_count": len(field),
    }
