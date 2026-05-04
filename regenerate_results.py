#!/usr/bin/env python3
"""
Regenerate results.csv from existing output.csv with updated formatter.
This avoids re-scraping LinkedIn profiles.
"""
import csv
import json
from formatter import format_work_history
from extractor import extract_jd_info

INPUT_FILE = "output.csv"
OUTPUT_FILE = "results.csv"

RESULTS_FIELDS = [
    "name", "site_page", "position", "email", "url", "locations_str",
    "status", "linkedin_url", "law_school", "jd_year", "work_history",
]


def derive_status(row: dict) -> str:
    """Derive status from row data."""
    if not row.get("linkedin_url"):
        return "Manual Review - no LinkedIn URL found"
    notes = row.get("notes", "")
    if notes:
        reason = notes.lstrip("* ").replace("MANUAL REVIEW -", "").strip()
        return f"Manual Review - {reason}"
    return "Match"


def regenerate():
    """Read output.csv and regenerate results.csv with updated formatter."""
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Processing {len(rows)} rows from {INPUT_FILE}...")

    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS)
        writer.writeheader()

        for i, row in enumerate(rows, 1):
            # Re-format work history with updated formatter
            formatted_wh = format_work_history(
                row.get('raw_profile_json', ''),
                row.get('url', '')
            )

            # Re-extract JD info (in case formatter improved this too)
            if row.get('raw_profile_json'):
                try:
                    profile = json.loads(row['raw_profile_json'])
                    law_school, jd_year = extract_jd_info(profile)
                except (json.JSONDecodeError, TypeError):
                    law_school, jd_year = None, None
            else:
                law_school, jd_year = None, None

            result_row = {
                "name": row["name"],
                "site_page": row["site_page"],
                "position": row["position"],
                "email": row.get("email", "") or "Not found",
                "url": row.get("url", "") or "Not found",
                "locations_str": row.get("locations_str", "") or "Not found",
                "status": derive_status(row),
                "linkedin_url": row["linkedin_url"] or "Not found",
                "law_school": law_school or "Not found",
                "jd_year": jd_year or "Not found",
                "work_history": formatted_wh or "Not found",
            }

            writer.writerow(result_row)

            if i % 10 == 0:
                print(f"  Processed {i}/{len(rows)}...")

    print(f"\n✓ Done! {OUTPUT_FILE} regenerated with updated formatter.")


if __name__ == "__main__":
    regenerate()
