from __future__ import annotations
from ..report.logging import log
from .datagolf_client import fetch_schedule, fetch_pre_tournament

def resolve_event(tour: str = "pga") -> dict:
    # choose next upcoming event from schedule then fetch pre-tournament to get field list
    sched = fetch_schedule(tour=tour, upcoming_only=True)
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

    pret = fetch_pre_tournament(event_id=int(event_id), tour=tour)
    players = pret.get("field") or pret.get("players") or pret.get("data") or []
    # normalize
    field=[]
    for p in players:
        name = p.get("player_name") or p.get("name") or p.get("player") or ""
        if not name: 
            continue
        field.append({"Player": name})

    return {
        "event_id": int(event_id),
        "event_name": event_name,
        "course": course,
        "date": date,
        "players": field,
        "field_count": len(field),
    }
