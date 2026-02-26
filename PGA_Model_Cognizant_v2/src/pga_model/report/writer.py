from __future__ import annotations
from pathlib import Path
import pandas as pd
from .logging import write_json, ensure_dir

def write_outputs(df: pd.DataFrame, summary: dict, calib: dict) -> None:
    ensure_dir("out")
    df.to_csv("out/model_table.csv", index=False)
    try:
        df.to_excel("out/model_table.xlsx", index=False)
    except Exception:
        pass
    write_json("out/summary.json", summary)
    write_json("out/calibration_report.json", calib)
