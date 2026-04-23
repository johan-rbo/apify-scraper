import csv
import json
import sys
import os
from scraper import get_linkedin_url, scrape_linkedin_profile
from extractor import extract_jd_info, extract_work_history, check_firm_match
from formatter import format_work_history


INPUT_FILE = "input.csv"
OUTPUT_FILE = "output.csv"
RESULTS_FILE = "results.csv"

RESULTS_FIELDS = [
    "name", "site_page", "position", "email", "url", "locations_str",
    "status", "linkedin_url", "law_school", "jd_year", "work_history",
]

OUTPUT_FIELDS = [
    "name",
    "site_page",
    "position",
    "email",
    "url",
    "locations_str",
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
    email = row.get("email", "").strip()
    firm_bio_link = row.get("url", "").strip()
    locations_str = row.get("locations_str", "").strip()

    result = {
        "name": name,
        "site_page": company,
        "position": position,
        "email": email,
        "url": firm_bio_link,
        "locations_str": locations_str,
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
    linkedin_url = get_linkedin_url(name, company, position, locations_str)
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
        result["notes"] = "* MANUAL REVIEW -firm not found in LinkedIn profile"
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


def _count_done_rows(filepath: str) -> int:
    """Return number of already-processed rows in a CSV (excluding header)."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


def _result_to_clean_row(r: dict) -> dict:
    def derive_status(r: dict) -> str:
        if not r.get("linkedin_url"):
            return "Manual Review - no LinkedIn URL found"
        notes = r.get("notes", "")
        if notes:
            reason = notes.lstrip("* ").replace("MANUAL REVIEW -", "").strip()
            return f"Manual Review - {reason}"
        return "Match"

    return {
        "name": r["name"],
        "site_page": r["site_page"],
        "position": r["position"],
        "email": r.get("email", "") or "Not found",
        "url": r.get("url", "") or "Not found",
        "locations_str": r.get("locations_str", "") or "Not found",
        "status": derive_status(r),
        "linkedin_url": r["linkedin_url"] or "Not found",
        "law_school": r["law_school"] or "Not found",
        "jd_year": r["jd_year"] or "Not found",
        "work_history": r["formatted_work_history"] or "Not found",
    }


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Create it with columns: name, site_page, position")
        sys.exit(1)

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    total = len(all_rows)
    done = _count_done_rows(OUTPUT_FILE)

    if done >= total:
        print(f"All {total} candidates already processed. Nothing to do.")
        return

    if done > 0:
        print(f"Resuming from candidate {done + 1}/{total} (skipping {done} already done)")
    else:
        print(f"Starting fresh. {total} candidates to process.")

    rows_to_process = all_rows[done:]

    output_is_new = done == 0
    results_is_new = _count_done_rows(RESULTS_FILE) == 0

    with open(OUTPUT_FILE, "a" if not output_is_new else "w", newline="", encoding="utf-8") as out_f, \
         open(RESULTS_FILE, "a" if not results_is_new else "w", newline="", encoding="utf-8") as res_f:

        out_writer = csv.DictWriter(out_f, fieldnames=OUTPUT_FIELDS)
        res_writer = csv.DictWriter(res_f, fieldnames=RESULTS_FIELDS)

        if output_is_new:
            out_writer.writeheader()
        if results_is_new:
            res_writer.writeheader()

        for i, row in enumerate(rows_to_process, start=done + 1):
            print(f"\n[{i}/{total}]", end="")
            result = process_row(row)
            out_writer.writerow(result)
            out_f.flush()
            res_writer.writerow(_result_to_clean_row(result))
            res_f.flush()

    print(f"\nDone. All {total} candidates processed.")


if __name__ == "__main__":
    main()
