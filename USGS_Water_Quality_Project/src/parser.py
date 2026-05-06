"""Parser for raw USGS or Water Quality Portal water quality CSV files.

The parser reads a manually downloaded CSV file, detects common column names,
cleans the records, and writes a smaller structured CSV used by the rest of the
project.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "usgs_water_quality_raw.csv"
CLEANED_PATH = PROJECT_ROOT / "data" / "cleaned" / "water_quality_cleaned.csv"

USEFUL_COLUMNS = [
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

COLUMN_CANDIDATES = {
    "site_id": [
        "MonitoringLocationIdentifier",
        "Monitoring Location Identifier",
        "site_no",
        "Site ID",
        "SiteID",
        "station_id",
        "Station ID",
        "LocationIdentifier",
    ],
    "site_name": [
        "MonitoringLocationName",
        "Monitoring Location Name",
        "station_nm",
        "Station Name",
        "Site Name",
        "site_name",
    ],
    "state": [
        "StateCode",
        "state_cd",
        "state",
        "State",
        "MonitoringLocationStateCode",
        "Monitoring Location State Code",
    ],
    "latitude": [
        "LatitudeMeasure",
        "ActivityLocation/LatitudeMeasure",
        "MonitoringLocation/LatitudeMeasure",
        "dec_lat_va",
        "DecimalLatitude",
        "Latitude",
        "lat",
    ],
    "longitude": [
        "LongitudeMeasure",
        "ActivityLocation/LongitudeMeasure",
        "MonitoringLocation/LongitudeMeasure",
        "dec_long_va",
        "DecimalLongitude",
        "Longitude",
        "lon",
        "long",
    ],
    "sample_date": [
        "ActivityStartDate",
        "sample_dt",
        "datetime",
        "Date",
        "Sample Date",
        "Activity Start Date",
    ],
    "characteristic": [
        "CharacteristicName",
        "Characteristic Name",
        "parameter",
        "parm_nm",
        "Parameter",
        "USGSPCode",
    ],
    "result_value": [
        "ResultMeasureValue",
        "Result Measure Value",
        "result_va",
        "value",
        "Value",
        "ResultValue",
    ],
    "unit": [
        "ResultMeasure/MeasureUnitCode",
        "ResultMeasure.MeasureUnitCode",
        "MeasureUnitCode",
        "unit_cd",
        "Unit",
        "unit",
    ],
}

STATE_NAMES = {
    "01": "Alabama",
    "02": "Alaska",
    "04": "Arizona",
    "05": "Arkansas",
    "06": "California",
    "08": "Colorado",
    "09": "Connecticut",
    "10": "Delaware",
    "11": "District of Columbia",
    "12": "Florida",
    "13": "Georgia",
    "15": "Hawaii",
    "16": "Idaho",
    "17": "Illinois",
    "18": "Indiana",
    "19": "Iowa",
    "20": "Kansas",
    "21": "Kentucky",
    "22": "Louisiana",
    "23": "Maine",
    "24": "Maryland",
    "25": "Massachusetts",
    "26": "Michigan",
    "27": "Minnesota",
    "28": "Mississippi",
    "29": "Missouri",
    "30": "Montana",
    "31": "Nebraska",
    "32": "Nevada",
    "33": "New Hampshire",
    "34": "New Jersey",
    "35": "New Mexico",
    "36": "New York",
    "37": "North Carolina",
    "38": "North Dakota",
    "39": "Ohio",
    "40": "Oklahoma",
    "41": "Oregon",
    "42": "Pennsylvania",
    "44": "Rhode Island",
    "45": "South Carolina",
    "46": "South Dakota",
    "47": "Tennessee",
    "48": "Texas",
    "49": "Utah",
    "50": "Vermont",
    "51": "Virginia",
    "53": "Washington",
    "54": "West Virginia",
    "55": "Wisconsin",
    "56": "Wyoming",
}

POSTAL_TO_STATE = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}


def normalize_column_name(name: object) -> str:
    """Return a simplified column name for robust matching."""
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def find_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Find the first column that matches one of the candidate names."""
    normalized_columns = {normalize_column_name(col): col for col in df.columns}

    for candidate in candidates:
        key = normalize_column_name(candidate)
        if key in normalized_columns:
            return normalized_columns[key]

    # Some exports include prefixes such as ActivityLocation/LatitudeMeasure.
    for candidate in candidates:
        key = normalize_column_name(candidate)
        for normalized, original in normalized_columns.items():
            if len(key) > 4 and normalized.endswith(key):
                return original

    return None


def clean_text(value: object) -> Optional[str]:
    """Strip text and convert empty values to missing values."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def normalize_state(value: object) -> Optional[str]:
    """Normalize common state formats to full state names when possible."""
    text = clean_text(value)
    if text is None:
        return None

    upper = text.upper()
    if upper.startswith("US:"):
        upper = upper.split(":", 1)[1]

    if upper in POSTAL_TO_STATE:
        return POSTAL_TO_STATE[upper]

    if upper.isdigit():
        return STATE_NAMES.get(upper.zfill(2), text)

    return text.title() if text.isupper() or text.islower() else text


def parse_numeric(value: object) -> Optional[float]:
    """Convert a raw measurement value to a float when possible.

    Values such as "<0.1" are converted to 0.1 so the record can still be used
    in simple range query experiments.
    """
    text = clean_text(value)
    if text is None:
        return None
    text = text.replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def build_cleaned_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Map raw columns to the project schema and clean the values."""
    mapped = {}
    selected_columns = {}

    for target_column, candidates in COLUMN_CANDIDATES.items():
        source_column = find_column(raw_df, candidates)
        selected_columns[target_column] = source_column
        if source_column is None:
            mapped[target_column] = pd.Series([None] * len(raw_df))
        else:
            mapped[target_column] = raw_df[source_column]

    cleaned = pd.DataFrame(mapped)

    for column in ["site_id", "site_name", "characteristic", "unit"]:
        cleaned[column] = cleaned[column].map(clean_text)

    cleaned["state"] = cleaned["state"].map(normalize_state)
    cleaned["latitude"] = cleaned["latitude"].map(parse_numeric)
    cleaned["longitude"] = cleaned["longitude"].map(parse_numeric)
    cleaned["result_value"] = cleaned["result_value"].map(parse_numeric)
    cleaned["sample_date"] = pd.to_datetime(cleaned["sample_date"], errors="coerce")

    cleaned = cleaned.dropna(
        subset=["site_id", "sample_date", "characteristic", "result_value"]
    )
    cleaned["sample_date"] = cleaned["sample_date"].dt.strftime("%Y-%m-%d")

    cleaned = cleaned[USEFUL_COLUMNS].reset_index(drop=True)

    print("Detected source columns:")
    for target_column, source_column in selected_columns.items():
        print(f"  {target_column}: {source_column if source_column else '[missing]'}")

    return cleaned


def print_statistics(raw_df: pd.DataFrame, cleaned_df: pd.DataFrame) -> None:
    """Print basic parser statistics for the milestone report."""
    print("\nParser statistics")
    print(f"Raw rows: {len(raw_df)}")
    print(f"Cleaned rows: {len(cleaned_df)}")
    print(f"Unique sites: {cleaned_df['site_id'].nunique()}")
    print(f"Unique characteristics: {cleaned_df['characteristic'].nunique()}")

    if cleaned_df.empty:
        print("Date range: [no cleaned records]")
    else:
        print(
            "Date range: "
            f"{cleaned_df['sample_date'].min()} to {cleaned_df['sample_date'].max()}"
        )

    print("\nMissing value summary in cleaned data:")
    print(cleaned_df.isna().sum().to_string())


def parse_raw_csv(raw_path: Path = RAW_PATH, cleaned_path: Path = CLEANED_PATH) -> pd.DataFrame:
    """Read the raw CSV and write the cleaned project dataset."""
    if not raw_path.exists():
        print("Please place usgs_water_quality_raw.csv in data/raw/")
        return pd.DataFrame(columns=USEFUL_COLUMNS)

    print(f"Reading raw data from {raw_path}")
    raw_df = pd.read_csv(raw_path, dtype=str, low_memory=False)
    cleaned_df = build_cleaned_dataframe(raw_df)

    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(cleaned_path, index=False)

    print_statistics(raw_df, cleaned_df)
    print(f"\nSaved cleaned data to {cleaned_path}")
    return cleaned_df


if __name__ == "__main__":
    parse_raw_csv()
