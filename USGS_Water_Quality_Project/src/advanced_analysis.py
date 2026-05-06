"""Additional analysis outputs for the USGS water quality project.

This script creates supporting outputs for data quality auditing, event-style
records, site profile vectors, and site similarity analysis. These outputs extend
the main query experiment without changing its baseline or optimized results.
"""

from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"
RAW = ROOT / "data" / "raw" / "usgs_water_quality_raw.csv"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"


def load_cleaned() -> pd.DataFrame:
    df = pd.read_csv(CLEANED)
    df["sample_date"] = pd.to_datetime(df["sample_date"], errors="coerce")
    df["result_value"] = pd.to_numeric(df["result_value"], errors="coerce")
    return df


def write_data_quality_audit(df: pd.DataFrame) -> None:
    rows = []
    for col in df.columns:
        rows.append({
            "column": col,
            "missing_count": int(df[col].isna().sum()),
            "missing_pct": round(float(df[col].isna().mean() * 100), 2),
            "unique_count": int(df[col].nunique(dropna=True)),
            "example_non_null_value": "" if df[col].dropna().empty else str(df[col].dropna().iloc[0])[:80],
        })
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "data_quality_audit.csv", index=False)


def write_spatiotemporal_event_view(df: pd.DataFrame) -> None:
    # The current WQP download has missing latitude/longitude, so this event view
    # keeps site_id as the location surrogate and records the limitation explicitly.
    events = df[["site_id", "sample_date", "characteristic", "result_value", "unit"]].copy()
    events.insert(0, "event_id", range(1, len(events) + 1))
    events.rename(columns={"site_id": "object_id", "sample_date": "timestamp", "result_value": "measurement_value"}, inplace=True)
    events.head(2000).to_csv(RESULTS / "spatiotemporal_event_view_sample.csv", index=False)


def write_site_vectors(df: pd.DataFrame) -> None:
    top_chars = df["characteristic"].value_counts().head(6).index.tolist()
    subset = df[df["characteristic"].isin(top_chars)]
    pivot = subset.pivot_table(index="site_id", columns="characteristic", values="result_value", aggfunc="mean")
    # Normalize each characteristic so one high-scale attribute does not dominate.
    normalized = pivot.copy()
    for col in normalized.columns:
        series = normalized[col]
        mean = series.mean(skipna=True)
        std = series.std(skipna=True)
        if std and not math.isnan(std):
            normalized[col] = (series - mean) / std
        else:
            normalized[col] = 0.0
    normalized = normalized.fillna(0.0)
    normalized.to_csv(RESULTS / "site_characteristic_vectors.csv")

    pairs = []
    ids = list(normalized.index)
    X = normalized.to_numpy(dtype=float)
    norms = np.linalg.norm(X, axis=1)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            denom = norms[i] * norms[j]
            sim = float(np.dot(X[i], X[j]) / denom) if denom else 0.0
            pairs.append({"site_a": ids[i], "site_b": ids[j], "cosine_similarity": round(sim, 4)})
    pd.DataFrame(pairs).sort_values("cosine_similarity", ascending=False).head(20).to_csv(RESULTS / "site_similarity_top20.csv", index=False)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    df = load_cleaned()
    write_data_quality_audit(df)
    write_spatiotemporal_event_view(df)
    write_site_vectors(df)
    print("Saved additional analysis outputs to results/ and results/figures/.")


if __name__ == "__main__":
    main()
