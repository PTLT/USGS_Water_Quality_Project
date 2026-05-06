# Efficient Range Query and Trend Analysis over USGS Water Quality Data

Final project by Edward Hu.

This project converts Water Quality Portal and USGS water quality records into a structured dataset, supports range-style queries, and compares a baseline linear scan query engine with an index-based query engine. The case study uses Cuyahoga County, Ohio with 12,400 cleaned records, 23 monitoring sites, and 242 measured characteristics from 2015-03-26 to 2024-02-06.

## Project Contents

```text
USGS_Water_Quality_Project_INTEGRATED/
  data/
    raw/usgs_water_quality_raw.csv
    cleaned/water_quality_cleaned.csv
  src/
    download_data.py
    parser.py
    data_loader.py
    scoring.py
    baseline.py
    optimized.py
    query_engine.py
    experiment.py
    visualization.py
    report_summary.py
    advanced_analysis.py
  results/
    runtime_results.csv
    scanned_count_results.csv
    query_metadata.csv
    summary_statistics.csv
    data_quality_audit.csv
    site_similarity_top20.csv
    figures/
  report/
    USGS_Water_Quality_Final_Report_INTEGRATED.docx
    build_integrated_report.py
  presentation/
    USGS_Water_Quality_7min_INTEGRATED.pptx
  requirements.txt
  run_project.sh
```

## Dataset Source

The data are downloaded from the Water Quality Portal using NWIS provider records. The default script downloads Cuyahoga County, Ohio records with these filters:

```text
statecode = US:39
countycode = US:39:035
providers = NWIS
sampleMedia = Water
startDateLo = 01-01-2015
startDateHi = 12-31-2024
dataProfile = resultPhysChem
mimeType = csv
```

## Cleaned Data Model

The parser maps the raw CSV into this structured schema:

```text
WaterQuality(
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
```

The SQLite helper uses the same fields and adds `record_id` as the primary key.

## Query Model

The query engine supports conjunctions of these predicates:

```text
state = value
site_id = value
characteristic = value
start_date <= sample_date <= end_date
min_value <= result_value <= max_value
```

For the final experiment, the simple query filters by characteristic, the medium query filters by characteristic plus numeric value range, and the complex query filters by characteristic plus numeric value range plus date range.

## Algorithms

The baseline algorithm scans every row and checks all active predicates, so its query cost is O(n).

The optimized algorithm builds dictionary indexes for state, site id, and characteristic, plus a sorted date index. It intersects candidate sets before applying value filters. Its filtering cost is O(c + r), where c is the candidate set size and r is the number of returned rows.

## How to Reproduce the Results

From the project root, run:

```bash
python3 -m pip install --user -r requirements.txt
python3 src/download_data.py --countycode US:39:035
python3 src/parser.py
python3 src/experiment.py
python3 src/visualization.py
python3 src/advanced_analysis.py
python3 report/build_integrated_report.py
```

Or run the helper script:

```bash
./run_project.sh
```

## Final Outputs

The main report is:

```text
report/USGS_Water_Quality_Final_Report_INTEGRATED.docx
```

The main experiment outputs are:

```text
results/runtime_results.csv
results/scanned_count_results.csv
results/query_metadata.csv
results/summary_statistics.csv
results/figures/runtime_by_dataset_size.png
results/figures/scanned_by_dataset_size.png
results/figures/trend_line.png
results/figures/value_histogram_log.png
results/figures/z_score_summary.png
```

The additional analysis script also creates data quality audit, event view, site vector, and site similarity outputs.

## Key Result Summary

Across all measured queries, the optimized method reduced scanned records by 87.93% and total runtime by 81.35% while returning the same result counts as the baseline method.
