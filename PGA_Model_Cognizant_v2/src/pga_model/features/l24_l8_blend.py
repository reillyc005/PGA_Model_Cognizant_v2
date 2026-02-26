from __future__ import annotations
import pandas as pd
import numpy as np
import re

SG_COLS = ["SG_OTT","SG_APP","SG_ARG","SG_PUTT","SG_TOTAL"]

def _norm(name: str) -> str:
    name = (name or "").lower().strip()
    name = re.sub(r"[^a-z\s\-']", "", name)
    name = re.sub(r"\s+", " ", name)
    return name

def _players(payload: dict) -> list[dict]:
    if isinstance(payload, dict):
        for k in ["players","data","rankings"]:
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return payload if isinstance(payload, list) else []

def _to_df(payload: dict) -> pd.DataFrame:
    rows=[]
    for p in _players(payload):
        name = p.get("player_name") or p.get("name") or p.get("player") or ""
        if not name: 
            continue
        row={"name_norm": _norm(name)}
        # DataGolf skill-ratings commonly exposes sg_* keys; be flexible
        for out, cands in {
            "SG_OTT":["sg_ott","sg_off_tee"],
            "SG_APP":["sg_app","sg_approach"],
            "SG_ARG":["sg_arg","sg_around_green"],
            "SG_PUTT":["sg_putt","sg_putting"],
            "SG_TOTAL":["sg_total","sg_t","sg_overall"]
        }.items():
            val=None
            for ck in cands:
                if ck in p:
                    val=p.get(ck); break
            row[out]=np.nan if val is None else float(val)
        rows.append(row)
    return pd.DataFrame(rows)

def blend(skill_l24: dict, skill_l8: dict | None, l24_weight: float=0.6, l8_weight: float=0.4) -> pd.DataFrame:
    df24=_to_df(skill_l24)
    if skill_l8 is None:
        return df24
    df8=_to_df(skill_l8)
    df=df24.merge(df8, on="name_norm", how="outer", suffixes=("_L24","_L8"))
    for c in SG_COLS:
        a=df.get(f"{c}_L24")
        b=df.get(f"{c}_L8")
        if a is None and b is None:
            df[c]=np.nan
        else:
            # renormalize over available
            w24=l24_weight if a is not None else 0.0
            w8=l8_weight if b is not None else 0.0
            df[c]=np.nan
            vals=[]
            weights=[]
            if f"{c}_L24" in df.columns:
                vals.append(df[f"{c}_L24"])
                weights.append(l24_weight)
            if f"{c}_L8" in df.columns:
                vals.append(df[f"{c}_L8"])
                weights.append(l8_weight)
            # row-wise
            out=[]
            for i in range(len(df)):
                vs=[]
                ws=[]
                if f"{c}_L24" in df.columns and not pd.isna(df.at[i,f"{c}_L24"]):
                    vs.append(df.at[i,f"{c}_L24"]); ws.append(l24_weight)
                if f"{c}_L8" in df.columns and not pd.isna(df.at[i,f"{c}_L8"]):
                    vs.append(df.at[i,f"{c}_L8"]); ws.append(l8_weight)
                if not vs:
                    out.append(np.nan)
                else:
                    s=sum(ws)
                    out.append(sum(v*w for v,w in zip(vs,ws))/s)
            df[c]=out
    return df[["name_norm"]+SG_COLS]
