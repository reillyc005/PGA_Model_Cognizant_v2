from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

from .report.logging import load_yaml, log, write_json, ensure_dir
from .fetch.field_resolver import resolve_event
from .fetch.datagolf_client import fetch_skill_ratings, fetch_player_decomp, fetch_approach_skill
from .features.build_features import build_features
from .features.weather import weather_adjustment
from .sim.simulate import compute_composite, simulate
from .report.calibration import calibration_report
from .report.writer import write_outputs

def cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="pretournament", choices=["pretournament"])
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    cfg = load_yaml("config/model.yaml")
    if args.seed is not None:
        cfg.setdefault("sim", {})["seed"] = int(args.seed)

    ensure_dir("out")
    Path("out/run.log").write_text("", encoding="utf-8")
    log("PGA_Model_Cognizant_v2 starting (pretournament)")

    try:
        ev = resolve_event()
        log(f"Event: {ev['event_name']} | Course: {ev['course']} | Field: {ev['field_count']}")

        skill_l24 = fetch_skill_ratings()
        # DataGolf doesn't expose true last-8 rounds here; we keep the L24/L8 blend interface.
        # If you later add a dedicated form endpoint, wire it into skill_l8.
        skill_l8 = None

        decomp = fetch_player_decomp()

        approach_l24 = fetch_approach_skill(period="l24")
        approach_l12 = fetch_approach_skill(period="l12")

        df = build_features(
            players=ev["players"],
            skill_l24=skill_l24,
            skill_l8=skill_l8,
            decomp=decomp,
            approach_l24=approach_l24,
            approach_l12=approach_l12,
            cfg=cfg
        )

        weather_adj = weather_adjustment(df, cap_abs=float(cfg["projection"]["approach"].get("weather_cap_abs", 0.12)))

        proj_weights = cfg["projection"]["weights"]
        comp = compute_composite(df, proj_weights)

        out_df = simulate(
            df=df,
            comp=comp,
            n_sims=int(cfg["sim"]["n_sims"]),
            seed=int(cfg["sim"]["seed"]),
            variance_multiplier=float(cfg["sim"].get("variance_multiplier", 1.0)),
            weather_adj=weather_adj
        )

        calib = calibration_report(out_df, cfg)
        summary = {
            "event": {k: ev.get(k) for k in ["event_id","event_name","course","date","field_count"]},
            "sim": cfg["sim"],
            "projection": cfg["projection"],
            "calibration_status": calib["status"],
        }

        if calib["status"] != "PASS":
            write_json("out/FAIL.json", calib)
            log("FAIL: guardrails triggered")
            write_outputs(out_df, summary, calib)
            return 2

        write_outputs(out_df, summary, calib)
        log("Done")
        return 0

    except Exception as e:
        err={"status":"FAIL","error":str(e)}
        write_json("out/FAIL.json", err)
        log(f"FATAL: {e}")
        return 3
