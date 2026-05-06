"""Generate figures for the final project report."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_cleaned_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
RUNTIME_RESULTS_PATH = RESULTS_DIR / "runtime_results.csv"
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"
SUMMARY_STATISTICS_PATH = RESULTS_DIR / "summary_statistics.csv"


def _save_current_figure(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved figure: {path}")


def _label_algorithm(name: str) -> str:
    return "Baseline linear scan" if name == "baseline_linear_scan" else "Optimized index"


def plot_runtime_comparison(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    grouped = (
        results_df.groupby(["query_type", "algorithm"])["runtime_seconds"]
        .mean()
        .unstack("algorithm")
    )
    grouped = grouped.rename(columns={c: _label_algorithm(c) for c in grouped.columns})
    grouped.plot(kind="bar", figsize=(9, 5))
    plt.title("Average Runtime by Query Type")
    plt.xlabel("Query type")
    plt.ylabel("Runtime seconds")
    plt.xticks(rotation=0)
    plt.legend(title="Algorithm")
    _save_current_figure(FIGURES_DIR / "runtime_comparison.png")


def plot_scanned_count_comparison(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    grouped = (
        results_df.groupby(["query_type", "algorithm"])["scanned_count"]
        .mean()
        .unstack("algorithm")
    )
    grouped = grouped.rename(columns={c: _label_algorithm(c) for c in grouped.columns})
    grouped.plot(kind="bar", figsize=(9, 5))
    plt.title("Average Scanned Record Count by Query Type")
    plt.xlabel("Query type")
    plt.ylabel("Scanned records")
    plt.xticks(rotation=0)
    plt.legend(title="Algorithm")
    _save_current_figure(FIGURES_DIR / "scanned_count_comparison.png")


def plot_runtime_by_dataset_size(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    plt.figure(figsize=(9, 5))
    for algorithm in ["baseline_linear_scan", "optimized_index"]:
        for query_type in ["simple", "medium", "complex"]:
            qdf = results_df[(results_df["algorithm"] == algorithm) & (results_df["query_type"] == query_type)]
            qdf = qdf.groupby("dataset_size")["runtime_seconds"].mean().reset_index()
            if not qdf.empty:
                label = f"{_label_algorithm(algorithm)}: {query_type}"
                plt.plot(qdf["dataset_size"], qdf["runtime_seconds"], marker="o", label=label)
    plt.title("Runtime by Dataset Size")
    plt.xlabel("Dataset size")
    plt.ylabel("Runtime seconds")
    plt.legend(fontsize=8)
    _save_current_figure(FIGURES_DIR / "runtime_by_dataset_size.png")


def plot_scanned_by_dataset_size(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return
    plt.figure(figsize=(9, 5))
    for algorithm in ["baseline_linear_scan", "optimized_index"]:
        subset = results_df[results_df["algorithm"] == algorithm]
        grouped = subset.groupby("dataset_size")["scanned_count"].mean().reset_index()
        if not grouped.empty:
            plt.plot(grouped["dataset_size"], grouped["scanned_count"], marker="o", label=_label_algorithm(algorithm))
    plt.title("Average Scanned Records by Dataset Size")
    plt.xlabel("Dataset size")
    plt.ylabel("Scanned records")
    plt.legend(title="Algorithm")
    _save_current_figure(FIGURES_DIR / "scanned_by_dataset_size.png")


def _selected_characteristic(df: pd.DataFrame) -> str | None:
    values = df["characteristic"].dropna()
    if values.empty:
        return None
    return str(values.mode().iloc[0])


def plot_trend_line(df: pd.DataFrame) -> None:
    if df.empty:
        return
    characteristic = _selected_characteristic(df)
    if characteristic is None:
        return
    subset = df[df["characteristic"].astype(str) == characteristic].copy()
    subset["sample_date"] = pd.to_datetime(subset["sample_date"], errors="coerce")
    subset["result_value"] = pd.to_numeric(subset["result_value"], errors="coerce")
    subset = subset.dropna(subset=["sample_date", "result_value"])
    if subset.empty:
        return
    daily = subset.groupby("sample_date")["result_value"].mean().reset_index().sort_values("sample_date")
    plt.figure(figsize=(9, 5))
    plt.plot(daily["sample_date"], daily["result_value"], marker="o", linewidth=1)
    if len(daily) >= 2:
        x = (daily["sample_date"] - daily["sample_date"].min()).dt.days.to_numpy()
        y = daily["result_value"].to_numpy()
        if len(set(x)) >= 2:
            slope, intercept = np.polyfit(x, y, 1)
            plt.plot(daily["sample_date"], slope * x + intercept, linestyle="--", label="Linear trend")
            plt.legend()
    plt.title(f"Trend Line for {characteristic}")
    plt.xlabel("Sample date")
    plt.ylabel("Mean result value")
    plt.xticks(rotation=30)
    _save_current_figure(FIGURES_DIR / "trend_line.png")


def plot_value_histogram(df: pd.DataFrame) -> None:
    if df.empty:
        return
    characteristic = _selected_characteristic(df)
    if characteristic is None:
        return
    values = pd.to_numeric(df[df["characteristic"].astype(str) == characteristic]["result_value"], errors="coerce").dropna()
    values = values[values > 0]
    if values.empty:
        return
    plt.figure(figsize=(8, 5))
    upper = max(float(values.max()), 10.0)
    lower = max(float(values.min()), 1e-6)
    bins = np.logspace(np.log10(lower), np.log10(upper), 30)
    plt.hist(values, bins=bins, edgecolor="black")
    plt.xscale("log")
    plt.title(f"Log Binned Distribution of {characteristic} Values")
    plt.xlabel("Result value, logarithmic scale")
    plt.ylabel("Frequency")
    _save_current_figure(FIGURES_DIR / "value_histogram_log.png")


def plot_z_score_summary() -> None:
    if not SUMMARY_STATISTICS_PATH.exists():
        return
    summary = pd.read_csv(SUMMARY_STATISTICS_PATH)
    if summary.empty:
        return
    top = summary.sort_values("count", ascending=False).iloc[0]
    mean = float(top["mean"])
    std = float(top["std"])
    max_value = float(top["max"])
    characteristic = str(top["characteristic"])
    if std <= 0:
        return
    labels = ["mean", "mean + 1 std", "mean + 2 std", "mean + 3 std", "max"]
    values = [mean, mean + std, mean + 2 * std, mean + 3 * std, max_value]
    plt.figure(figsize=(9, 5))
    plt.bar(labels, values)
    plt.title(f"Z Score Context for {characteristic}")
    plt.ylabel("Result value")
    plt.xticks(rotation=20)
    _save_current_figure(FIGURES_DIR / "z_score_summary.png")


def main() -> None:
    if not RUNTIME_RESULTS_PATH.exists():
        print("Experiment results not found. Please run python3 src/experiment.py first.")
        results_df = pd.DataFrame()
    else:
        results_df = pd.read_csv(RUNTIME_RESULTS_PATH)
    df = load_cleaned_data(CLEANED_PATH)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plot_runtime_comparison(results_df)
    plot_scanned_count_comparison(results_df)
    plot_runtime_by_dataset_size(results_df)
    plot_scanned_by_dataset_size(results_df)
    plot_trend_line(df)
    plot_value_histogram(df)
    plot_z_score_summary()


if __name__ == "__main__":
    main()
