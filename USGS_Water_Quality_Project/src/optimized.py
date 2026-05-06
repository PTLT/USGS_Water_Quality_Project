"""Index based query processing for water quality records."""

from __future__ import annotations

import bisect
import time
from collections import defaultdict
from typing import Any

import pandas as pd

from baseline import summarize_sites


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


class IndexedWaterQualityEngine:
    """In memory indexed query engine for water quality records.

    The optimized method is faster than a full linear scan because state, site,
    characteristic, and date indexes reduce the candidate set before value
    filtering and aggregation are applied.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy().reset_index(drop=True)
        self.df["sample_date"] = pd.to_datetime(self.df["sample_date"], errors="coerce")
        self.df["result_value"] = pd.to_numeric(self.df["result_value"], errors="coerce")

        self.state_index: dict[str, set[int]] = defaultdict(set)
        self.site_index: dict[str, set[int]] = defaultdict(set)
        self.characteristic_index: dict[str, set[int]] = defaultdict(set)
        self.date_values: list[pd.Timestamp] = []
        self.date_rows: list[int] = []

        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build simple dictionary and sorted-date indexes."""
        date_pairs = []

        for index, row in self.df.iterrows():
            state = _normalize_text(row.get("state"))
            site_id = _normalize_text(row.get("site_id"))
            characteristic = _normalize_text(row.get("characteristic"))

            if state:
                self.state_index[state].add(index)
            if site_id:
                self.site_index[site_id].add(index)
            if characteristic:
                self.characteristic_index[characteristic].add(index)

            sample_date = row.get("sample_date")
            if pd.notna(sample_date):
                date_pairs.append((sample_date, index))

        date_pairs.sort(key=lambda item: item[0])
        self.date_values = [item[0] for item in date_pairs]
        self.date_rows = [item[1] for item in date_pairs]

    def _date_candidates(
        self, start_date: pd.Timestamp | None, end_date: pd.Timestamp | None
    ) -> set[int]:
        """Return row indexes whose dates fall inside the requested window."""
        if start_date is None and end_date is None:
            return set(range(len(self.df)))

        left = 0
        right = len(self.date_values)
        if start_date is not None:
            left = bisect.bisect_left(self.date_values, start_date)
        if end_date is not None:
            right = bisect.bisect_right(self.date_values, end_date)

        return set(self.date_rows[left:right])

    def _candidate_indexes(self, query: dict) -> tuple[set[int], dict]:
        """Intersect relevant indexes to find a small candidate set."""
        prepared_query = {
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

        candidate_sets = []
        if prepared_query["state"] is not None:
            candidate_sets.append(self.state_index.get(prepared_query["state"], set()))
        if prepared_query["site_id"] is not None:
            candidate_sets.append(self.site_index.get(prepared_query["site_id"], set()))
        if prepared_query["characteristic"] is not None:
            candidate_sets.append(
                self.characteristic_index.get(prepared_query["characteristic"], set())
            )
        if prepared_query["start_date"] is not None or prepared_query["end_date"] is not None:
            candidate_sets.append(
                self._date_candidates(prepared_query["start_date"], prepared_query["end_date"])
            )

        if not candidate_sets:
            return set(range(len(self.df))), prepared_query

        candidate_sets.sort(key=len)
        candidates = set(candidate_sets[0])
        for candidate_set in candidate_sets[1:]:
            candidates.intersection_update(candidate_set)
            if not candidates:
                break

        return candidates, prepared_query

    def range_query(self, query: dict) -> tuple[pd.DataFrame, int, float]:
        """Run an indexed range query and return records, scanned count, runtime."""
        start_time = time.perf_counter()
        candidates, prepared_query = self._candidate_indexes(query)

        matched_indexes = []
        for index in candidates:
            row = self.df.iloc[index]
            sample_date = row.get("sample_date")
            result_value = row.get("result_value")

            if pd.isna(sample_date) or pd.isna(result_value):
                continue

            if (
                prepared_query["start_date"] is not None
                and sample_date < prepared_query["start_date"]
            ):
                continue
            if prepared_query["end_date"] is not None and sample_date > prepared_query["end_date"]:
                continue
            if (
                prepared_query["min_value"] is not None
                and result_value < prepared_query["min_value"]
            ):
                continue
            if (
                prepared_query["max_value"] is not None
                and result_value > prepared_query["max_value"]
            ):
                continue

            matched_indexes.append(index)

        runtime_seconds = time.perf_counter() - start_time
        matched_records = self.df.loc[matched_indexes].copy()
        scanned_count = len(candidates)
        return matched_records, scanned_count, runtime_seconds

    def topk_sites(self, query: dict, k: int = 10) -> pd.DataFrame:
        """Return top k site summaries using the indexed range query."""
        matched_records, _, _ = self.range_query(query)
        return summarize_sites(matched_records, k=k, rank_by=query.get("rank_by", "count"))
