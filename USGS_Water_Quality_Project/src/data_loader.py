"""Loading utilities for the cleaned water quality dataset."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality.sqlite"


def load_cleaned_data(path: str | Path = DEFAULT_CLEANED_PATH) -> pd.DataFrame:
    """Load the cleaned CSV dataset into a pandas DataFrame."""
    path = Path(path)
    if not path.exists():
        print("Please run python src/parser.py first.")
        return pd.DataFrame(
            columns=[
                "site_id",
                "site_name",
                "state",
                "latitude",
                "longitude",
                "sample_date",
                "characteristic",
                "result_value",
                "unit",
            ]
        )

    df = pd.read_csv(path)
    df["sample_date"] = pd.to_datetime(df["sample_date"], errors="coerce")
    df["result_value"] = pd.to_numeric(df["result_value"], errors="coerce")
    return df


def save_to_sqlite(df: pd.DataFrame, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Save cleaned records into a simple SQLite relational table."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS WaterQuality (
            record_id INTEGER PRIMARY KEY,
            site_id TEXT,
            site_name TEXT,
            state TEXT,
            latitude REAL,
            longitude REAL,
            sample_date TEXT,
            characteristic TEXT,
            result_value REAL,
            unit TEXT
        )
        """
    )
    cursor.execute("DELETE FROM WaterQuality")

    rows = []
    for _, row in df.iterrows():
        sample_date = row.get("sample_date")
        if pd.notna(sample_date):
            sample_date = pd.to_datetime(sample_date).strftime("%Y-%m-%d")
        else:
            sample_date = None

        rows.append(
            (
                row.get("site_id"),
                row.get("site_name"),
                row.get("state"),
                row.get("latitude"),
                row.get("longitude"),
                sample_date,
                row.get("characteristic"),
                row.get("result_value"),
                row.get("unit"),
            )
        )

    cursor.executemany(
        """
        INSERT INTO WaterQuality (
            site_id,
            site_name,
            state,
            latitude,
            longitude,
            sample_date,
            characteristic,
            result_value,
            unit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()
    connection.close()
    print(f"Saved {len(rows)} records to {db_path}")


def load_from_sqlite(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Load records from the SQLite WaterQuality table."""
    db_path = Path(db_path)
    if not db_path.exists():
        print(f"SQLite database not found: {db_path}")
        return pd.DataFrame()

    connection = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM WaterQuality", connection)
    connection.close()

    df["sample_date"] = pd.to_datetime(df["sample_date"], errors="coerce")
    df["result_value"] = pd.to_numeric(df["result_value"], errors="coerce")
    return df


if __name__ == "__main__":
    data = load_cleaned_data()
    if not data.empty:
        save_to_sqlite(data)
