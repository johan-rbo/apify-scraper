import csv
import json
import sys
import os
from scraper import get_linkedin_url, scrape_linkedin_profile
from extractor import extract_jd_info, extract_work_history, check_firm_match
from formatter import format_work_history
import preview

INPUT_FILE = "input.csv"
OUTPUT_FILE = "output.csv"

OUTPUT_FIELDS = [
    "name",
    "site_page",
    "position",
    "linkedin_url",
    "jd_year",
    "law_school",
    "work_history",
    "formatted_work_history",
    "notes",
    "raw_profile_json",
]


def process_row(row: dict) -> dict:
    name = row.get("name", "").strip()
    company = row.get("site_page", "").strip()
    position = row.get("position", "").strip()

    firm_bio_link = row.get("firm_bio_link", "").strip()

    result = {
        "name": name,
        "site_page": company,
        "position": position,
        "linkedin_url": "",
        "jd_year": "",
        "law_school": "",
        "work_history": "",
        "formatted_work_history": "",
        "notes": "",
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

    # Step 3: extract work history (always, so flagged rows also show what firm IS listed)
    work_history = extract_work_history(profile)
    result["work_history"] = json.dumps(work_history, ensure_ascii=False)

    # Step 4: verify the LinkedIn profile actually lists the firm we searched for
    firm_matched = check_firm_match(profile, company)
    if not firm_matched:
        print(f"  WARNING — firm '{company}' not found in LinkedIn profile. Flagging for manual review.")
        result["notes"] = "* MANUAL REVIEW — firm not found in LinkedIn profile"
        return result

    # Step 5: generate formatted work history via Claude
    print("  [AI] Formatting work history...")
    result["formatted_work_history"] = format_work_history(
        result["raw_profile_json"], firm_bio_link
    )

    # Step 6: extract JD year and law school from education JSON
    law_school, jd_year = extract_jd_info(profile)
    result["law_school"] = law_school or ""
    result["jd_year"] = jd_year or ""

    print(f"  Law school: {law_school}  |  JD year: {jd_year}")
    return result


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Create it with columns: name, site_page, position")
        sys.exit(1)

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {INPUT_FILE}")

    rows = rows[:5]  # TEST: limit to first 5 rows
    results = []
    for row in rows:
        result = process_row(row)
        results.append(result)

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. Results saved to {OUTPUT_FILE}\n")
    preview.run(OUTPUT_FILE)


if __name__ == "__main__":
    main()
