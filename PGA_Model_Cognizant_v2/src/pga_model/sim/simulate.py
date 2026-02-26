from __future__ import annotations
import numpy as np
import pandas as pd

def _z(x: pd.Series) -> pd.Series:
    v = x.astype(float)
    sd = v.std(ddof=0, skipna=True)
    if sd == 0 or np.isnan(sd):
        return pd.Series(np.zeros(len(v)), index=v.index)
    return (v - v.mean(skipna=True)) / sd

def compute_composite(df: pd.DataFrame, proj_weights: dict) -> pd.Series:
    comp = pd.Series(0.0, index=df.index)
    wsum = 0.0

    # positive features
    for key in ["SG_TOTAL","APPROACH_WEIGHTED","COURSE_HISTORY","COURSE_FIT","PENALTY_AVOID"]:
        w = float(proj_weights.get(key, 0.0))
        if w > 0 and key in df.columns and df[key].notna().any():
            comp += w * _z(df[key])
            wsum += w

    # negative features
    for key, col in [("BIG_NUM","BIG_NUM"),("STABILITY","STD_DEV")]:
        w = float(proj_weights.get(key, 0.0))
        if w > 0 and col in df.columns and df[col].notna().any():
            comp -= w * _z(df[col])
            wsum += w

    if wsum <= 0:
        return pd.Series(np.zeros(len(df)), index=df.index)
    return comp / wsum

def simulate(df: pd.DataFrame, comp: pd.Series, n_sims: int, seed: int, variance_multiplier: float=1.0, weather_adj: pd.Series|None=None):
    rng = np.random.default_rng(seed)
    n = len(df)

    # per-player sigma
    if "STD_DEV" in df.columns and df["STD_DEV"].notna().any():
        sig = df["STD_DEV"].fillna(df["STD_DEV"].median()).to_numpy(dtype=float)
        sig = np.clip(sig, 1.5, 6.0)
    else:
        sig = np.full(n, 3.0, dtype=float)

    sig = sig * float(variance_multiplier)

    mu = comp.to_numpy(dtype=float)
    # scale to strokes/round spread
    target_sd = 1.2
    mu_sd = np.std(mu)
    if mu_sd > 0:
        mu = mu * (target_sd / mu_sd)

    if weather_adj is not None:
        mu = mu + weather_adj.to_numpy(dtype=float)

    draws = rng.normal(loc=mu, scale=sig, size=(n_sims, n))
    ranks = draws.argsort(axis=1)[:, ::-1]

    cutline = min(70, n-1)
    cuts = {"T10":10,"T20":20,"T30":30,"T40":40}
    counts = {k: np.zeros(n, dtype=int) for k in cuts}
    made = np.zeros(n, dtype=int)

    for s in range(n_sims):
        order = ranks[s]
        for k,t in cuts.items():
            counts[k][order[:t]] += 1
        made[order[:cutline]] += 1

    out = df.copy()
    out["MODEL_SCORE"] = mu
    out["P_MC"] = made / n_sims
    for k in cuts:
        out[f"P_{k}"] = counts[k] / n_sims

    # monotonicity enforce
    out["P_T10"] = np.minimum(out["P_T10"], out["P_T20"])
    out["P_T20"] = np.minimum(out["P_T20"], out["P_T30"])
    out["P_T30"] = np.minimum(out["P_T30"], out["P_T40"])

    return out
