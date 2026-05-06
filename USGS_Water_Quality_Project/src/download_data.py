"""Download a Water Quality Portal CSV file for this project.

The project can also use a manually downloaded file. This script is optional,
but it makes the data collection step reproducible.

Default query:
- Ohio water quality sample results
- NWIS provider
- physical/chemical result profile
- water samples
- 2015-01-01 to 2024-12-31

The downloaded file is saved as data/raw/usgs_water_quality_raw.csv so that
src/parser.py can read it directly.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "usgs_water_quality_raw.csv"
BASE_URL = "https://www.waterqualitydata.us/data/Result/search"


def build_query_url(
    statecode: str,
    countycode: str,
    start_date: str,
    end_date: str,
    provider: str,
    characteristic: str | None,
    output_path: Path,
) -> str:
    """Build a Water Quality Portal Result service URL."""
    params: list[tuple[str, str]] = [
        ("statecode", statecode),
        ("providers", provider),
        ("sampleMedia", "Water"),
        ("startDateLo", start_date),
        ("startDateHi", end_date),
        ("dataProfile", "resultPhysChem"),
        ("mimeType", "csv"),
        ("zip", "no"),
        ("sorted", "no"),
    ]

    if countycode:
        params.append(("countycode", countycode))
    if characteristic:
        params.append(("characteristicName", characteristic))

    return BASE_URL + "?" + urllib.parse.urlencode(params)


def download_file(url: str, output_path: Path) -> None:
    """Download a CSV file from Water Quality Portal."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading Water Quality Portal data...")
    print(f"URL: {url}")

    try:
        with urllib.request.urlopen(url, timeout=180) as response:
            status = getattr(response, "status", None)
            if status and status >= 400:
                raise RuntimeError(f"HTTP status {status}")
            data = response.read()
    except Exception as exc:  # pragma: no cover - depends on network access
        raise SystemExit(
            "Download failed. Use the printed URL in a browser, download the CSV, "
            "and save it as data/raw/usgs_water_quality_raw.csv. "
            f"Error: {exc}"
        ) from exc

    if len(data) < 100 or b"," not in data[:2000]:
        raise SystemExit(
            "The downloaded response did not look like a CSV file. Try a smaller "
            "date range, a county filter, or manual download from the WQP website."
        )

    output_path.write_bytes(data)
    print(f"Saved raw CSV to {output_path}")
    print("Next step: python3 src/parser.py")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download WQP data for the project.")
    parser.add_argument("--statecode", default="US:39", help="WQP state code, e.g. US:39 for Ohio.")
    parser.add_argument(
        "--countycode",
        default="",
        help="Optional WQP county code, e.g. US:39:035 for Cuyahoga County.",
    )
    parser.add_argument("--start-date", default="01-01-2015", help="Start date in MM-DD-YYYY.")
    parser.add_argument("--end-date", default="12-31-2024", help="End date in MM-DD-YYYY.")
    parser.add_argument("--provider", default="NWIS", help="WQP provider, usually NWIS or WQX.")
    parser.add_argument(
        "--characteristic",
        default="",
        help="Optional characteristic filter, e.g. pH. Leave blank for all characteristics.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    output_path = Path(args.output)
    url = build_query_url(
        statecode=args.statecode,
        countycode=args.countycode,
        start_date=args.start_date,
        end_date=args.end_date,
        provider=args.provider,
        characteristic=args.characteristic or None,
        output_path=output_path,
    )
    download_file(url, output_path)


if __name__ == "__main__":
    main()
