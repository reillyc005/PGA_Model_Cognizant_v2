from __future__ import annotations
import pandas as pd

def calibration_report(df: pd.DataFrame, cfg: dict) -> dict:
    g = cfg.get("guardrails", {}) or {}
    n = len(df)
    fill_pct = float(df.get("FILL_PLAYER", pd.Series([False]*n)).mean()) if n else 0.0

    probs = {
        "max_p_t10": float(df["P_T10"].max()) if "P_T10" in df.columns else None,
        "max_p_t40": float(df["P_T40"].max()) if "P_T40" in df.columns else None,
        "max_p_mc": float(df["P_MC"].max()) if "P_MC" in df.columns else None,
    }

    status = "PASS"
    reasons = []

    if fill_pct > float(g.get("max_fill_player_pct_fail", 0.5)):
        status = "FAIL"
        reasons.append(f"Fill player pct too high: {fill_pct:.3f}")

    if probs["max_p_t10"] is not None and probs["max_p_t10"] > float(g.get("max_p_t10", 0.55)):
        status = "FAIL"; reasons.append("max P(T10) too high")
    if probs["max_p_t40"] is not None and probs["max_p_t40"] > float(g.get("max_p_t40", 0.85)):
        status = "FAIL"; reasons.append("max P(T40) too high")
    if probs["max_p_mc"] is not None and probs["max_p_mc"] > float(g.get("max_p_mc", 0.95)):
        status = "FAIL"; reasons.append("max P(MC) too high")

    return {
        "status": status,
        "n_players": n,
        "fill_player_pct": fill_pct,
        "prob_sanity": probs,
        "reasons": reasons,
    }
