"""Simple command line query interface for the project."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from baseline import baseline_range_query
from data_loader import load_cleaned_data
from optimized import IndexedWaterQualityEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"


def _normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _read_input(prompt: str) -> str:
    return input(prompt).strip()


def _print_examples(df: pd.DataFrame, column: str, entered_value: str) -> None:
    """Print examples when a requested state or characteristic does not exist."""
    if entered_value.strip() == "" or column not in df.columns:
        return

    available = sorted({str(value) for value in df[column].dropna().unique()})
    normalized_available = {_normalize_text(value) for value in available}
    if _normalize_text(entered_value) not in normalized_available:
        examples = ", ".join(available[:10]) if available else "[none]"
        print(f"{column} '{entered_value}' was not found. Available examples: {examples}")


def collect_query_from_user() -> tuple[dict, int]:
    """Ask the user for query fields. Blank fields are ignored."""
    print("Enter query values. Leave a field blank to ignore that condition.\n")
    query = {
        "state": _read_input("State (example: Ohio): "),
        "site_id": _read_input("Site ID: "),
        "characteristic": _read_input("Characteristic (example: pH): "),
        "start_date": _read_input("Start date YYYY-MM-DD: "),
        "end_date": _read_input("End date YYYY-MM-DD: "),
        "min_value": _read_input("Minimum value: "),
        "max_value": _read_input("Maximum value: "),
    }

    k_text = _read_input("k for top sites [10]: ")
    if k_text == "":
        k = 10
    else:
        try:
            k = int(k_text)
        except ValueError:
            print("Invalid k. Using k = 10.")
            k = 10

    return query, k


def print_results(
    baseline_records: pd.DataFrame,
    baseline_scanned: int,
    baseline_runtime: float,
    optimized_records: pd.DataFrame,
    optimized_scanned: int,
    optimized_runtime: float,
    top_sites: pd.DataFrame,
) -> None:
    """Display query results and performance information."""
    print("\nQuery performance")
    print(f"Baseline result count: {len(baseline_records)}")
    print(f"Baseline runtime seconds: {baseline_runtime:.6f}")
    print(f"Baseline scanned records: {baseline_scanned}")
    print(f"Optimized result count: {len(optimized_records)}")
    print(f"Optimized runtime seconds: {optimized_runtime:.6f}")
    print(f"Optimized scanned records: {optimized_scanned}")

    if len(baseline_records) != len(optimized_records):
        print("Warning: baseline and optimized result counts differ.")

    if optimized_records.empty:
        print("\nNo records matched this query.")
    else:
        display_columns = [
            "site_id",
            "site_name",
            "state",
            "sample_date",
            "characteristic",
            "result_value",
            "unit",
        ]
        print("\nFirst matching records")
        print(optimized_records[display_columns].head(10).to_string(index=False))

    print("\nTop site summary")
    if top_sites.empty:
        print("[no matching sites]")
    else:
        print(top_sites.to_string(index=False))


def main() -> None:
    """Load data, collect a query, and compare baseline with optimized search."""
    df = load_cleaned_data(CLEANED_PATH)
    if df.empty:
        return

    query, k = collect_query_from_user()
    _print_examples(df, "state", query.get("state", ""))
    _print_examples(df, "characteristic", query.get("characteristic", ""))

    try:
        baseline_records, baseline_scanned, baseline_runtime = baseline_range_query(df, query)
        engine = IndexedWaterQualityEngine(df)
        optimized_records, optimized_scanned, optimized_runtime = engine.range_query(query)
        top_sites = engine.topk_sites(query, k=k)
    except ValueError as error:
        print(error)
        return

    print_results(
        baseline_records,
        baseline_scanned,
        baseline_runtime,
        optimized_records,
        optimized_scanned,
        optimized_runtime,
        top_sites,
    )


if __name__ == "__main__":
    main()
