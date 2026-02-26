from __future__ import annotations
import pandas as pd
import numpy as np
import re

from .l24_l8_blend import blend as blend_sg, SG_COLS
from .course_history import extract_course_history
from .similar_courses import compute_course_fit

def _norm(name: str) -> str:
    name=(name or "").lower().strip()
    name=re.sub(r"[^a-z\s\-']", "", name)
    name=re.sub(r"\s+"," ",name)
    return name

def _players(payload: dict) -> list[dict]:
    if isinstance(payload, dict):
        for k in ["players","data","rankings","field"]:
            if isinstance(payload.get(k), list):
                return payload[k]
    return payload if isinstance(payload, list) else []

def _extract_approach(payload: dict) -> pd.DataFrame:
    rows=[]
    for p in _players(payload):
        name = p.get("player_name") or p.get("name") or p.get("player") or ""
        if not name: 
            continue
        row={"name_norm": _norm(name)}
        # Try common DG bucket keys (varies by schema). We look for 150-200 and 200+ equivalents.
        # Accept either structured buckets or flat keys.
        buckets = p.get("distance_buckets") or p.get("buckets")
        if isinstance(buckets, list):
            for b in buckets:
                lo=b.get("min_yards"); hi=b.get("max_yards")
                if lo is None or hi is None: 
                    continue
                sg=b.get("sg_per_shot") or b.get("sg") or b.get("sg_app")
                poor=b.get("poor_shot_avoid_pct") or b.get("poor_shot_avoidance") or b.get("poor_shot_avoid")
                key=f"{int(lo)}_{int(hi)}"
                if sg is not None:
                    row[f"sg_{key}"]=float(sg)
                if poor is not None:
                    row[f"poor_avoid_{key}"]=float(poor)
        # Flat keys fallbacks
        for k,v in p.items():
            if isinstance(v,(int,float)) and k.startswith("sg_"):
                row[k]=float(v)
            if isinstance(v,(int,float)) and ("poor" in k and "avoid" in k):
                row[k]=float(v)
        # overall poor shot avoid if present
        for cand in ["poor_shot_avoid_pct","poor_shot_avoidance","poor_shot_avoid"]:
            if cand in p and p[cand] is not None:
                row["poor_avoid_overall"]=float(p[cand])
                break
        return_rows=True
        rows.append(row)
    return pd.DataFrame(rows)

def _bucket_value(ap_df: pd.DataFrame, lo: int, hi: int) -> pd.Series:
    # Prefer exact sg_lo_hi column; else try approximate match
    exact=f"sg_{lo}_{hi}"
    if exact in ap_df.columns:
        return ap_df[exact]
    # sometimes 150_200 or 200_999 style
    for c in ap_df.columns:
        if c.startswith("sg_") and str(lo) in c and str(hi) in c:
            return ap_df[c]
    return pd.Series([np.nan]*len(ap_df), index=ap_df.index)

def _poor_avoid_value(ap_df: pd.DataFrame) -> pd.Series:
    if "poor_avoid_overall" in ap_df.columns:
        return ap_df["poor_avoid_overall"]
    # fall back to any poor_avoid_* column mean
    cols=[c for c in ap_df.columns if c.startswith("poor_avoid_")]
    if cols:
        return ap_df[cols].mean(axis=1, skipna=True)
    return pd.Series([np.nan]*len(ap_df), index=ap_df.index)

def build_features(players: list[dict], skill_l24: dict, skill_l8: dict|None, decomp: dict|None,
                   approach_l24: dict|None, approach_l12: dict|None,
                   cfg: dict) -> pd.DataFrame:
    df=pd.DataFrame(players)
    df["name_norm"]=df["Player"].apply(_norm)

    # SG blend
    sg=blend_sg(skill_l24, skill_l8, cfg["sg_blend"]["l24_weight"], cfg["sg_blend"]["l8_weight"])
    df=df.merge(sg, on="name_norm", how="left")

    # Decomp: STD_DEV, BIG_NUM
    df["STD_DEV"]=np.nan; df["BIG_NUM"]=np.nan
    if decomp:
        dplist=_players(decomp)
        dp=pd.DataFrame(dplist)
        if not dp.empty:
            if "player_name" in dp.columns and "Player" not in dp.columns:
                dp["Player"]=dp["player_name"]
            dp["name_norm"]=dp["Player"].apply(_norm)
            for cand in ["std_dev","std_deviation","round_std_dev"]:
                if cand in dp.columns:
                    df=df.merge(dp[["name_norm",cand]].rename(columns={cand:"STD_DEV"}), on="name_norm", how="left", suffixes=("","_y"))
                    df["STD_DEV"]=df["STD_DEV"].fillna(df.get("STD_DEV_y"))
                    if "STD_DEV_y" in df.columns: df=df.drop(columns=["STD_DEV_y"])
                    break
            for cand in ["big_num","big_numbers","big_num_rate","dbl_bogey_rate"]:
                if cand in dp.columns:
                    df=df.merge(dp[["name_norm",cand]].rename(columns={cand:"BIG_NUM"}), on="name_norm", how="left", suffixes=("","_y"))
                    df["BIG_NUM"]=df["BIG_NUM"].fillna(df.get("BIG_NUM_y"))
                    if "BIG_NUM_y" in df.columns: df=df.drop(columns=["BIG_NUM_y"])
                    break

    # Course history
    ch=extract_course_history(decomp)
    df=df.merge(ch, on="name_norm", how="left")
    if "COURSE_HISTORY" not in df.columns: df["COURSE_HISTORY"]=np.nan

    # Course fit placeholder
    df["COURSE_FIT"]=compute_course_fit(df)

    # Approach skill (DataGolf-compliant): blend l24 + l12, then distance weight 150-200 vs 200+
    df["APPROACH_WEIGHTED"]=np.nan
    df["POOR_SHOT_AVOID"]=np.nan
    if approach_l24 or approach_l12:
        ap24=_extract_approach(approach_l24) if approach_l24 else pd.DataFrame(columns=["name_norm"])
        ap12=_extract_approach(approach_l12) if approach_l12 else pd.DataFrame(columns=["name_norm"])
        ap=ap24.merge(ap12, on="name_norm", how="outer", suffixes=("_l24","_l12"))

        # buckets
        b150_200 = ap.get("sg_150_200_l24") if "sg_150_200_l24" in ap.columns else None
        # general fetch using helper
        if b150_200 is None:
            # reconstruct temporary dfs for helper use
            pass

        # Use helper bucket series from each period, then blend
        def bucket_from(ap_df, lo, hi, suffix):
            # attempt exact
            col=f"sg_{lo}_{hi}{suffix}"
            if col in ap_df.columns: return ap_df[col]
            # search
            for c in ap_df.columns:
                if c.startswith("sg_") and c.endswith(suffix) and str(lo) in c and str(hi) in c:
                    return ap_df[c]
            return pd.Series([np.nan]*len(ap_df), index=ap_df.index)

        s150_200_l24 = bucket_from(ap,150,200,"_l24")
        s150_200_l12 = bucket_from(ap,150,200,"_l12")
        # 200+ is tricky; often labeled 200_999 or 200_plus. We'll try several.
        def bucket_200p(ap_df, suffix):
            # exact common
            for cand in [f"sg_200_999{suffix}", f"sg_200_plus{suffix}", f"sg_200_300{suffix}", f"sg_200_275{suffix}"]:
                if cand in ap_df.columns: return ap_df[cand]
            for c in ap_df.columns:
                if c.startswith("sg_") and c.endswith(suffix) and ("200" in c and ("999" in c or "plus" in c or "275" in c or "300" in c)):
                    return ap_df[c]
            return pd.Series([np.nan]*len(ap_df), index=ap_df.index)
        s200p_l24 = bucket_200p(ap,"_l24")
        s200p_l12 = bucket_200p(ap,"_l12")

        w_l24 = float(cfg["projection"]["approach"]["period_blend"]["l24"])
        w_l12 = float(cfg["projection"]["approach"]["period_blend"]["l12"])

        def blend_series(a,b):
            out=[]
            for i in range(len(ap)):
                vs=[]; ws=[]
                va=a.iat[i] if i < len(a) else np.nan
                vb=b.iat[i] if i < len(b) else np.nan
                if not pd.isna(va): vs.append(va); ws.append(w_l24)
                if not pd.isna(vb): vs.append(vb); ws.append(w_l12)
                if not vs: out.append(np.nan)
                else:
                    s=sum(ws)
                    out.append(sum(v*w for v,w in zip(vs,ws))/s)
            return pd.Series(out, index=ap.index)

        s150_200 = blend_series(s150_200_l24, s150_200_l12)
        s200p = blend_series(s200p_l24, s200p_l12)

        # poor shot avoid (overall) blend if available
        poor_l24 = ap.get("poor_avoid_overall_l24") if "poor_avoid_overall_l24" in ap.columns else pd.Series([np.nan]*len(ap), index=ap.index)
        poor_l12 = ap.get("poor_avoid_overall_l12") if "poor_avoid_overall_l12" in ap.columns else pd.Series([np.nan]*len(ap), index=ap.index)
        poor = blend_series(poor_l24, poor_l12)

        ap_out=pd.DataFrame({"name_norm": ap["name_norm"], "b150_200": s150_200, "b200p": s200p, "poor": poor})
        # zscore buckets across field (only on available)
        def z(v):
            x=v.astype(float)
            m=x.mean(skipna=True); sd=x.std(ddof=0, skipna=True)
            if sd==0 or np.isnan(sd): return pd.Series([0.0]*len(x), index=x.index)
            return (x-m)/sd
        z150=z(ap_out["b150_200"]); z200=z(ap_out["b200p"])
        w150=float(cfg["projection"]["approach"]["distance_weights"]["150_200"])
        w200=float(cfg["projection"]["approach"]["distance_weights"]["200_plus"])
        # renormalize if missing
        aw=[]
        for i in range(len(ap_out)):
            parts=[]
            if not pd.isna(z150.iat[i]): parts.append((z150.iat[i], w150))
            if not pd.isna(z200.iat[i]): parts.append((z200.iat[i], w200))
            if not parts:
                aw.append(np.nan)
            else:
                sw=sum(w for _,w in parts)
                aw.append(sum(v*w for v,w in parts)/sw)
        ap_out["APPROACH_WEIGHTED"]=aw
        df=df.merge(ap_out[["name_norm","APPROACH_WEIGHTED","poor"]].rename(columns={"poor":"POOR_SHOT_AVOID"}), on="name_norm", how="left")

    # Penalty avoid feature: combine poor-shot avoid (positive) and BIG_NUM (negative)
    # z-score later in composite; just keep raw
    df["PENALTY_AVOID"]=np.nan
    df["PENALTY_AVOID"]=df["POOR_SHOT_AVOID"]
    # if POOR_SHOT_AVOID missing, derive from -BIG_NUM
    mask=df["PENALTY_AVOID"].isna() & df["BIG_NUM"].notna()
    df.loc[mask,"PENALTY_AVOID"] = -df.loc[mask,"BIG_NUM"]

    # coverage flags (simple)
    df["FILL_PLAYER"]=df[SG_COLS+["STD_DEV","BIG_NUM"]].isna().all(axis=1)

    return df
