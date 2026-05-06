"""Summary statistics, trend analysis, and anomaly scoring functions."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _as_dataframe(records) -> pd.DataFrame:
    """Convert supported record containers to a DataFrame."""
    if isinstance(records, pd.DataFrame):
        return records.copy()
    return pd.DataFrame(records)


def compute_summary(records) -> dict:
    """Compute count, mean, min, max, and standard deviation."""
    df = _as_dataframe(records)
    if df.empty or "result_value" not in df.columns:
        return {"count": 0, "mean": None, "min": None, "max": None, "std": None}

    values = pd.to_numeric(df["result_value"], errors="coerce").dropna()
    if values.empty:
        return {"count": 0, "mean": None, "min": None, "max": None, "std": None}

    return {
        "count": int(values.count()),
        "mean": float(values.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "std": float(values.std(ddof=0)),
    }


def compute_trend_slope(records) -> float:
    """Estimate a simple linear trend slope over time.

    The date is converted into the number of days since the first observation.
    A positive slope means the measurement tends to increase over time, while a
    negative slope means it tends to decrease.
    """
    df = _as_dataframe(records)
    if df.empty or "sample_date" not in df.columns or "result_value" not in df.columns:
        return 0.0

    dates = pd.to_datetime(df["sample_date"], errors="coerce")
    values = pd.to_numeric(df["result_value"], errors="coerce")
    trend_df = pd.DataFrame({"sample_date": dates, "result_value": values}).dropna()

    if len(trend_df) < 2:
        return 0.0

    trend_df = trend_df.sort_values("sample_date")
    day_index = (trend_df["sample_date"] - trend_df["sample_date"].min()).dt.days

    if day_index.nunique() < 2:
        return 0.0

    slope, _ = np.polyfit(day_index.to_numpy(dtype=float), trend_df["result_value"], 1)
    return float(slope)


def compute_anomaly_score(value: float, mean: float, std: float) -> float:
    """Compute an absolute z score anomaly value."""
    if value is None or mean is None or std is None:
        return 0.0
    if pd.isna(value) or pd.isna(mean) or pd.isna(std):
        return 0.0
    if math.isclose(float(std), 0.0):
        return 0.0
    return abs(float(value) - float(mean)) / float(std)
