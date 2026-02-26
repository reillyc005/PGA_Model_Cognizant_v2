from __future__ import annotations
import pandas as pd
import numpy as np
import re

def _norm(name: str) -> str:
    name=(name or "").lower().strip()
    name=re.sub(r"[^a-z\s\-']", "", name)
    name=re.sub(r"\s+"," ",name)
    return name

def extract_course_history(decomp_payload: dict | None) -> pd.DataFrame:
    if not decomp_payload:
        return pd.DataFrame(columns=["name_norm","COURSE_HISTORY"])
    players = None
    if isinstance(decomp_payload, dict):
        for k in ["players","data"]:
            if isinstance(decomp_payload.get(k), list):
                players = decomp_payload[k]; break
    if players is None and isinstance(decomp_payload, list):
        players = decomp_payload
    if not isinstance(players, list):
        return pd.DataFrame(columns=["name_norm","COURSE_HISTORY"])

    rows=[]
    for p in players:
        name=p.get("player_name") or p.get("name") or p.get("player") or ""
        if not name: continue
        ch=None
        for cand in ["course_history_adj","course_history","course_hist","ch_adj"]:
            if cand in p and p[cand] is not None:
                try: ch=float(p[cand]); break
                except: pass
        rows.append({"name_norm": _norm(name), "COURSE_HISTORY": np.nan if ch is None else ch})
    return pd.DataFrame(rows)
