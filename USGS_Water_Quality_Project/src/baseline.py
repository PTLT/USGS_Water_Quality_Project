"""Baseline linear scan query algorithms."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def _parse_date(value: Any, field_name: str) -> pd.Timestamp | None:
    if _is_blank(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"Invalid {field_name}: {value}")
    return parsed


def _parse_float(value: Any, field_name: str) -> float | None:
    if _is_blank(value):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value}") from exc


def _prepare_query(query: dict) -> dict:
    """Convert query text fields into comparable Python values."""
    return {
        "state": _normalize_text(query.get("state")) if not _is_blank(query.get("state")) else None,
        "site_id": _normalize_text(query.get("site_id")) if not _is_blank(query.get("site_id")) else None,
        "characteristic": (
            _normalize_text(query.get("characteristic"))
            if not _is_blank(query.get("characteristic"))
            else None
        ),
        "start_date": _parse_date(query.get("start_date"), "start_date"),
        "end_date": _parse_date(query.get("end_date"), "end_date"),
        "min_value": _parse_float(query.get("min_value"), "min_value"),
        "max_value": _parse_float(query.get("max_value"), "max_value"),
    }


def _row_matches(row: pd.Series, prepared_query: dict) -> bool:
    """Check whether one row satisfies all active query conditions."""
    state = prepared_query["state"]
    site_id = prepared_query["site_id"]
    characteristic = prepared_query["characteristic"]
    start_date = prepared_query["start_date"]
    end_date = prepared_query["end_date"]
    min_value = prepared_query["min_value"]
    max_value = prepared_query["max_value"]

    if state is not None and _normalize_text(row.get("state")) != state:
        return False
    if site_id is not None and _normalize_text(row.get("site_id")) != site_id:
        return False
    if characteristic is not None and _normalize_text(row.get("characteristic")) != characteristic:
        return False

    sample_date = pd.to_datetime(row.get("sample_date"), errors="coerce")
    if pd.isna(sample_date):
        return False
    if start_date is not None and sample_date < start_date:
        return False
    if end_date is not None and sample_date > end_date:
        return False

    result_value = pd.to_numeric(row.get("result_value"), errors="coerce")
    if pd.isna(result_value):
        return False
    if min_value is not None and result_value < min_value:
        return False
    if max_value is not None and result_value > max_value:
        return False

    return True


def baseline_range_query(df: pd.DataFrame, query: dict) -> tuple[pd.DataFrame, int, float]:
    """Run a linear scan range query over every record in the DataFrame."""
    start_time = time.perf_counter()
    prepared_query = _prepare_query(query)

    matched_indexes = []
    for index, row in df.iterrows():
        if _row_matches(row, prepared_query):
            matched_indexes.append(index)

    runtime_seconds = time.perf_counter() - start_time
    matched_records = df.loc[matched_indexes].copy()
    scanned_count = len(df)
    return matched_records, scanned_count, runtime_seconds


def summarize_sites(records: pd.DataFrame, k: int = 10, rank_by: str = "count") -> pd.DataFrame:
    """Group matched records by site and return a top k site summary."""
    if records.empty:
        return pd.DataFrame(
            columns=["site_id", "site_name", "count", "mean", "min", "max", "std"]
        )

    summary = (
        records.groupby(["site_id", "site_name"], dropna=False)["result_value"]
        .agg(count="count", mean="mean", min="min", max="max", std="std")
        .reset_index()
    )
    summary["std"] = summary["std"].fillna(0.0)

    if rank_by == "mean":
        summary = summary.sort_values(["mean", "count"], ascending=[False, False])
    else:
        summary = summary.sort_values(["count", "mean"], ascending=[False, False])

    return summary.head(k).reset_index(drop=True)


def baseline_topk_sites(df: pd.DataFrame, query: dict, k: int = 10) -> pd.DataFrame:
    """Return top k sites after filtering records with the baseline algorithm."""
    matched_records, _, _ = baseline_range_query(df, query)
    return summarize_sites(matched_records, k=k, rank_by=query.get("rank_by", "count"))
