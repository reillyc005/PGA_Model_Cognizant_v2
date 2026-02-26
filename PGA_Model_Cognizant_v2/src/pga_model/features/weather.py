from __future__ import annotations
import pandas as pd
import numpy as np

def weather_adjustment(df: pd.DataFrame, cap_abs: float = 0.12) -> pd.Series:
    # Pre-tournament stub: keep weather overlay deterministic and bounded.
    # If you later connect a weather client, convert exposure into strokes and clip to cap_abs.
    adj = pd.Series(np.zeros(len(df)), index=df.index, name="WEATHER_ADJ")
    return adj.clip(lower=-abs(cap_abs), upper=abs(cap_abs))
