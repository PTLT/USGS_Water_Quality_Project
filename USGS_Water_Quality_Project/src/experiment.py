"""Experiments comparing baseline and indexed range query algorithms.

The size experiment uses deterministic random samples at 1,000, 5,000,
10,000, and full-dataset scale. The simple query filters by characteristic,
the medium query adds a numeric value range, and the complex query adds both
a numeric value range and a date range selected from the same target
characteristic.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from baseline import baseline_range_query
from data_loader import load_cleaned_data
from optimized import IndexedWaterQualityEngine
from scoring import compute_trend_slope


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"
RESULTS_DIR = PROJECT_ROOT / "results"
RUNTIME_RESULTS_PATH = RESULTS_DIR / "runtime_results.csv"
SCANNED_RESULTS_PATH = RESULTS_DIR / "scanned_count_results.csv"
SUMMARY_STATISTICS_PATH = RESULTS_DIR / "summary_statistics.csv"
QUERY_METADATA_PATH = RESULTS_DIR / "query_metadata.csv"
RANDOM_SEED = 42


def _most_common_value(df: pd.DataFrame, column: str) -> str | None:
    if column not in df.columns:
        return None
    values = df[column].dropna()
    if values.empty:
        return None
    return str(values.mode().iloc[0])


def _value_range(df: pd.DataFrame) -> tuple[float | None, float | None]:
    values = pd.to_numeric(df["result_value"], errors="coerce").dropna()
    if values.empty:
        return None, None
    # Use 5th and 95th percentiles so the value predicate is meaningful but not too narrow.
    return float(values.quantile(0.05)), float(values.quantile(0.95))


def _target_date_window(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Return a robust date window for the target characteristic.

    The window is computed from the same characteristic used by the query.
    This keeps the complex query selective while avoiding empty date ranges
    caused by sparse sampling dates.
    """
    dates = pd.to_datetime(df["sample_date"], errors="coerce").dropna()
    if dates.empty:
        return None, None
    end_date = dates.max()
    start_date = end_date - pd.DateOffset(years=2)
    window_count = ((dates >= start_date) & (dates <= end_date)).sum()
    if window_count == 0:
        start_date = dates.min()
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def build_queries(df: pd.DataFrame) -> list[tuple[str, str, dict]]:
    """Create simple, medium, and complex queries from available values."""
    characteristic = _most_common_value(df, "characteristic")
    if characteristic is None:
        return []

    target_rows = df[df["characteristic"].astype(str) == characteristic].copy()
    min_value, max_value = _value_range(target_rows)
    start_date, end_date = _target_date_window(target_rows)

    return [
        (
            "simple",
            "characteristic",
            {"characteristic": characteristic},
        ),
        (
            "medium",
            "characteristic_value_range",
            {
                "characteristic": characteristic,
                "min_value": min_value,
                "max_value": max_value,
            },
        ),
        (
            "complex",
            "characteristic_value_date_range",
            {
                "characteristic": characteristic,
                "start_date": start_date,
                "end_date": end_date,
                "min_value": min_value,
                "max_value": max_value,
            },
        ),
    ]


def dataset_sizes(total_rows: int) -> list[int]:
    requested_sizes = [1000, 5000, 10000, total_rows]
    usable_sizes = []
    for size in requested_sizes:
        if size <= total_rows and size not in usable_sizes:
            usable_sizes.append(size)
    return usable_sizes


def sample_subset(df: pd.DataFrame, size: int) -> pd.DataFrame:
    """Return a deterministic random sample for a fair size experiment."""
    if size >= len(df):
        return df.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)
    return df.sample(n=size, random_state=RANDOM_SEED).reset_index(drop=True)


def save_summary_statistics(df: pd.DataFrame) -> None:
    rows = []
    grouped = df.groupby(["state", "characteristic"], dropna=False)

    for (state, characteristic), group in grouped:
        values = pd.to_numeric(group["result_value"], errors="coerce").dropna()
        if values.empty:
            continue
        rows.append(
            {
                "state": state,
                "characteristic": characteristic,
                "count": int(values.count()),
                "mean": float(values.mean()),
                "min": float(values.min()),
                "max": float(values.max()),
                "std": float(values.std(ddof=0)),
                "trend_slope": compute_trend_slope(group),
            }
        )

    summary_df = pd.DataFrame(rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["count"], ascending=False)
    summary_df.to_csv(SUMMARY_STATISTICS_PATH, index=False)
    print(f"Saved summary statistics to {SUMMARY_STATISTICS_PATH}")


def run_experiments() -> pd.DataFrame:
    df = load_cleaned_data(CLEANED_PATH)
    if df.empty:
        return pd.DataFrame()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save_summary_statistics(df)
    results = []
    metadata_rows = []

    for size in dataset_sizes(len(df)):
        subset = sample_subset(df, size)
        queries = build_queries(subset)
        engine = IndexedWaterQualityEngine(subset)

        for query_type, query_shape, query in queries:
            baseline_records, baseline_scanned, baseline_runtime = baseline_range_query(subset, query)
            optimized_records, optimized_scanned, optimized_runtime = engine.range_query(query)

            if len(baseline_records) != len(optimized_records):
                print(
                    "Warning: result count mismatch for "
                    f"size={size}, query_type={query_type}, query_shape={query_shape}"
                )

            metadata_rows.append(
                {
                    "dataset_size": size,
                    "query_type": query_type,
                    "query_shape": query_shape,
                    "characteristic": query.get("characteristic"),
                    "start_date": query.get("start_date"),
                    "end_date": query.get("end_date"),
                    "min_value": query.get("min_value"),
                    "max_value": query.get("max_value"),
                }
            )

            for algorithm, runtime, scanned, record_count in [
                ("baseline_linear_scan", baseline_runtime, baseline_scanned, len(baseline_records)),
                ("optimized_index", optimized_runtime, optimized_scanned, len(optimized_records)),
            ]:
                results.append(
                    {
                        "dataset_size": size,
                        "query_type": query_type,
                        "query_shape": query_shape,
                        "algorithm": algorithm,
                        "runtime_seconds": runtime,
                        "scanned_count": scanned,
                        "result_count": record_count,
                    }
                )

    results_df = pd.DataFrame(results)
    results_df.to_csv(RUNTIME_RESULTS_PATH, index=False)
    results_df[
        [
            "dataset_size",
            "query_type",
            "query_shape",
            "algorithm",
            "scanned_count",
            "result_count",
        ]
    ].to_csv(SCANNED_RESULTS_PATH, index=False)
    pd.DataFrame(metadata_rows).drop_duplicates().to_csv(QUERY_METADATA_PATH, index=False)

    print("\nExperiment summary")
    if results_df.empty:
        print("[no experiment results]")
    else:
        summary = (
            results_df.groupby(["query_type", "algorithm"])[
                ["runtime_seconds", "scanned_count", "result_count"]
            ]
            .mean(numeric_only=True)
            .reset_index()
        )
        print(summary.to_string(index=False))
        zero_rows = results_df[(results_df["query_type"] == "complex") & (results_df["result_count"] == 0)]
        if not zero_rows.empty:
            print("Warning: at least one complex query returned zero records. Consider widening the date window.")
        print(f"\nSaved runtime results to {RUNTIME_RESULTS_PATH}")
        print(f"Saved scanned count results to {SCANNED_RESULTS_PATH}")
        print(f"Saved query metadata to {QUERY_METADATA_PATH}")

    return results_df


if __name__ == "__main__":
    run_experiments()
