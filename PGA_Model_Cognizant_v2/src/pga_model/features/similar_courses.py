from __future__ import annotations
import pandas as pd
import numpy as np

def compute_course_fit(df: pd.DataFrame) -> pd.Series:
    # Placeholder similarity course fit: if you want to add a trait model later, wire here.
    # For now, return zeros so the pipeline is stable and automation-ready.
    return pd.Series(np.zeros(len(df)), index=df.index, name="COURSE_FIT")
