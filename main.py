import csv
import json
import sys
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from scraper import get_linkedin_url, scrape_linkedin_profile
from extractor import extract_jd_info

OUTPUT_FIELDS = [
    "name",
    "site_page",
    "position",
    "linkedin_url",
    "jd_year",
    "law_school",
    "raw_profile_json",
]


def process_row(row: dict) -> dict:
    name = row.get("name", "").strip()
    company = row.get("site_page", "").strip()
    position = row.get("position", "").strip()

    result = {
        "name": name,
        "site_page": company,
        "position": position,
        "linkedin_url": "",
        "jd_year": "",
        "law_school": "",
        "raw_profile_json": "",
    }

    print(f"\nProcessing: {name} | {company} | {position}")

    # Step 1: find LinkedIn URL via SERP
    linkedin_url = get_linkedin_url(name, company, position)
    if not linkedin_url:
        print("  Skipping — no LinkedIn URL found.")
        return result

    result["linkedin_url"] = linkedin_url

    # Step 2: scrape LinkedIn profile
    profile = scrape_linkedin_profile(linkedin_url)
    if not profile:
        print("  Skipping — no profile data returned.")
        return result

    result["raw_profile_json"] = json.dumps(profile, ensure_ascii=False)

    # Step 3: extract JD year and law school from education JSON
    law_school, jd_year = extract_jd_info(profile)
    result["law_school"] = law_school or ""
    result["jd_year"] = jd_year or ""

    print(f"  Law school: {law_school}  |  JD year: {jd_year}")
    return result


def pick_input_file() -> str:
    """Open a file dialog to select the input CSV."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select input CSV file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    root.destroy()
    if not path:
        print("No file selected. Exiting.")
        sys.exit(0)
    return path


def pick_output_file() -> str:
    """Open a save dialog to choose output file name and location."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.asksaveasfilename(
        title="Save output CSV as",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        initialfile="output.csv",
    )
    root.destroy()
    if not path:
        print("No output file selected. Exiting.")
        sys.exit(0)
    return path


def main():
    input_file = pick_input_file()

    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nLoaded {len(rows)} rows from {input_file}")

    results = []
    for row in rows:
        result = process_row(row)
        results.append(result)

    output_file = pick_output_file()

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. Results saved to {output_file}")


if __name__ == "__main__":
    main()
