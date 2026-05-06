#!/bin/bash
set -e
python3 -m pip install --user -r requirements.txt
python3 src/download_data.py --countycode US:39:035
python3 src/parser.py
python3 src/experiment.py
python3 src/visualization.py
python3 src/advanced_analysis.py
python3 report/build_integrated_report.py
open report/USGS_Water_Quality_Final_Report_INTEGRATED.docx
