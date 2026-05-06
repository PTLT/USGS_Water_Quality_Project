"""Create a report-ready summary from cleaned data and experiment outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"
RUNTIME_RESULTS_PATH = PROJECT_ROOT / "results" / "runtime_results.csv"
SUMMARY_STATISTICS_PATH = PROJECT_ROOT / "results" / "summary_statistics.csv"
REPORT_VALUES_PATH = PROJECT_ROOT / "results" / "report_values.md"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _percent_reduction(baseline: float, optimized: float) -> float | None:
    if baseline <= 0:
        return None
    return (baseline - optimized) / baseline * 100.0


def build_report_values() -> str:
    cleaned = _safe_read_csv(CLEANED_PATH)
    runtime = _safe_read_csv(RUNTIME_RESULTS_PATH)
    summary = _safe_read_csv(SUMMARY_STATISTICS_PATH)

    lines: list[str] = []
    lines.append("# Report Values to Copy into Final Report")
    lines.append("")

    if cleaned.empty:
        lines.append("## Dataset Statistics")
        lines.append("Cleaned data is missing. Run `python3 src/parser.py` first.")
    else:
        cleaned["sample_date"] = pd.to_datetime(cleaned["sample_date"], errors="coerce")
        lines.append("## Dataset Statistics")
        lines.append(f"- Cleaned records: {len(cleaned):,}")
        lines.append(f"- Unique monitoring sites: {cleaned['site_id'].nunique():,}")
        lines.append(f"- Unique characteristics: {cleaned['characteristic'].nunique():,}")
        lines.append(
            f"- Date range: {cleaned['sample_date'].min().date()} to {cleaned['sample_date'].max().date()}"
        )
        state_values = cleaned["state"].dropna()
        if state_values.empty:
            lines.append("- Study region: Cuyahoga County, Ohio (countycode US:39:035)")
        else:
            lines.append(f"- Most common state: {state_values.mode().iloc[0]}")
        lines.append(f"- Most common characteristic: {cleaned['characteristic'].mode().iloc[0]}")

    lines.append("")
    if runtime.empty:
        lines.append("## Experiment Results")
        lines.append("Experiment output is missing. Run `python3 src/experiment.py` first.")
    else:
        lines.append("## Experiment Results")
        pivot = runtime.pivot_table(
            index=["dataset_size", "query_type", "date_window"],
            columns="algorithm",
            values=["runtime_seconds", "scanned_count", "result_count"],
            aggfunc="mean",
        )
        lines.append(pivot.to_markdown())

        if "baseline_linear_scan" in runtime["algorithm"].unique() and "optimized_index" in runtime["algorithm"].unique():
            merged = runtime.pivot_table(
                index=["dataset_size", "query_type", "date_window"],
                columns="algorithm",
                values=["runtime_seconds", "scanned_count"],
                aggfunc="mean",
            ).reset_index()
            reductions = []
            for _, row in merged.iterrows():
                try:
                    scan_reduction = _percent_reduction(
                        float(row[("scanned_count", "baseline_linear_scan")]),
                        float(row[("scanned_count", "optimized_index")]),
                    )
                    runtime_reduction = _percent_reduction(
                        float(row[("runtime_seconds", "baseline_linear_scan")]),
                        float(row[("runtime_seconds", "optimized_index")]),
                    )
                except Exception:
                    continue
                if scan_reduction is not None:
                    reductions.append((scan_reduction, runtime_reduction))
            if reductions:
                avg_scan = sum(item[0] for item in reductions) / len(reductions)
                runtime_values = [item[1] for item in reductions if item[1] is not None]
                lines.append("")
                lines.append(f"- Average scanned-count reduction: {avg_scan:.2f}%")
                if runtime_values:
                    avg_runtime = sum(runtime_values) / len(runtime_values)
                    lines.append(f"- Average runtime reduction: {avg_runtime:.2f}%")

    lines.append("")
    if summary.empty:
        lines.append("## Trend Analysis")
        lines.append("Summary statistics are missing. Run `python3 src/experiment.py` first.")
    else:
        top = summary.sort_values("count", ascending=False).iloc[0]
        lines.append("## Trend Analysis")
        selected_state = top.get("state", "Cuyahoga County, Ohio")
        if pd.isna(selected_state) or str(selected_state).strip() == "":
            selected_state = "Cuyahoga County, Ohio"
        lines.append(f"- Selected region: {selected_state}")
        lines.append(f"- Selected characteristic: {top['characteristic']}")
        lines.append(f"- Count: {int(top['count']):,}")
        lines.append(f"- Mean: {float(top['mean']):.4f}")
        lines.append(f"- Standard deviation: {float(top['std']):.4f}")
        lines.append(f"- Trend slope: {float(top['trend_slope']):.8f} units per day")

    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_VALUES_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = build_report_values()
    REPORT_VALUES_PATH.write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved report values to {REPORT_VALUES_PATH}")


if __name__ == "__main__":
    main()
