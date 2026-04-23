#!/usr/bin/env python3
"""
Work History Formatter — Standalone Python Script
Replicates the Affirm Partners Clay column logic for formatting
LinkedIn work history data via Claude API.

Usage:
  python work_history_formatter.py --linkedin "raw linkedin text" [--firm-bio-link "https://kirkland.com/..."]
  python work_history_formatter.py --file input.json           # batch mode
  python work_history_formatter.py --csv input.csv             # CSV batch mode

Requires:
  pip install anthropic

Set your API key:
  export ANTHROPIC_API_KEY=sk-ant-...
"""

import argparse
import json
import csv
import sys
import os

try:
    import anthropic
except ImportError:
    print("ERROR: 'anthropic' package not installed. Run: pip install anthropic")
    sys.exit(1)


# ---------------------------------------------------------------------------
# The prompt — ported directly from the Clay column / Marco's email spec
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a work history formatter for an elite legal recruiting firm. You will be given raw LinkedIn experience data for an attorney. Your job is to reformat it into a clean, standardized format that provides an accurate and comprehensive picture of the candidate's legal career progression.

## Output Format

Each role goes on its own line, ordered from most recent to earliest:

Title, Firm Name (City, Month Year - Month Year)

If the person was promoted to Partner at any firm, add this at the very end:

Partner since:
Month Year

## Title Rules
- Simplify ALL titles to their generic version:
  - Any type of Associate (e.g., "M&A Associate", "Private Equity and M&A Associate", "Corporate Finance Associate", "Senior Associate", "Senior Attorney", "Practice Area Attorney") → Associate
  - Any type of Partner (e.g., "Equity Partner", "Managing Partner", "Executive Compensation Partner", "Shareholder") → Partner
  - "Attorney" → Associate
  - Keep "Counsel", "Senior Counsel", and "Trainee Lawyer" as-is
  - "Special Counsel" → Counsel
  - For clerkships: Law Clerk, Hon. [Judge Name], [Court Name]
- Each role/promotion at the same firm gets its own line (e.g., Associate → Counsel → Partner at the same firm = 3 lines)

## Firm Name Rules
- Drop "LLP", "LLC", "P.C.", and similar entity designations from all firm names
- Keep the full firm name otherwise (e.g., "Skadden, Arps, Slate, Meagher & Flom" not just "Skadden")

## What to Include
- Law firm positions
- In-house counsel roles (title format: [Title], [Company Name])
- Federal clerkships
- Secondment roles

## What to Exclude
- Summer associate roles
- Fellowships
- Internships / externships
- Non-federal clerkship experience
- Government roles (other than clerkships)
- Consulting, accounting, or non-legal jobs
- Education entries
- Membership organizations
- Mini pupillages

## Location Rules
- Use city only (e.g., "New York" not "New York, New York, United States")
- If no city is listed, omit the city from the parenthetical
- Include city inside the parenthetical: (City, Month Year - Month Year)

## Date Rules
- Use the format: Month Year (e.g., Oct 2020)
- Use "Present" for current roles
- If only a year is available with no month, just use the year

## Partner Since Rules
- If the person holds or held a Partner title at any firm, include a "Partner since:" section at the bottom
- The date should be the earliest date they became Partner at any firm
- If there is no Partner title, do not include this section

## Stability Tag

AFTER the formatted career history, add a one-line summary:

STABILITY: [Stable / Some movement / Unstable] — [total number of firms] firms in [years since law school graduation] years post-JD

Use these definitions:
- Stable = 1-2 firms, or 3 firms with each stint 3+ years
- Some movement = 3-4 firms with at least one stint under 2 years
- Unstable = 5+ firms, OR multiple stints under 1 year, OR clear pattern of short stays

If you cannot determine years post-JD from the data, omit the "in X years post-JD" portion.

## Flags
Add flags at the bottom when you spot potential issues:
- ⚠️ Gap flag: If there's an unexplained gap of 6+ months between roles
- ⚠️ Long tenure flag: If someone was at the same firm 10+ years with no promotion shown — likely made Partner before lateraling
- ⚠️ Title jump flag: If someone went from Associate at Firm A directly to Partner at Firm B — may have made Partner at Firm A first

## Firm Bio Cross-Check

If a Firm Bio Link is provided, extract the firm name from the domain using these mappings:
- kirkland.com → Kirkland & Ellis
- lw.com → Latham & Watkins
- skadden.com → Skadden, Arps, Slate, Meagher & Flom
- weil.com → Weil, Gotshal & Manges
- sullcrom.com → Sullivan & Cromwell
- davispolk.com → Davis Polk & Wardwell
- cravath.com → Cravath, Swaine & Moore
- sidley.com → Sidley Austin
- gibsondunn.com → Gibson, Dunn & Crutcher
- jonesday.com → Jones Day
- velaw.com → Vinson & Elkins
- bracewell.com → Bracewell
- haynesboone.com → Haynes and Boone
- akingump.com → Akin Gump Strauss Hauer & Feld
- wlrk.com → Wachtell, Lipton, Rosen & Katz
- paulweiss.com → Paul, Weiss, Rifkind, Wharton & Garrison
- clearygottlieb.com → Cleary Gottlieb Steen & Hamilton
- milbank.com → Milbank
- shearman.com → Shearman & Sterling
- whitecase.com → White & Case
- morganlewis.com → Morgan, Lewis & Bockius
- klgates.com → K&L Gates
- huntonak.com → Hunton Andrews Kurth
- bakerbotts.com → Baker Botts
- lockelord.com → Locke Lord
- winston.com → Winston & Strawn
- porterhedges.com → Porter Hedges
- tklaw.com → Thompson & Knight
- nortonrosefulbright.com → Norton Rose Fulbright

For any domain not listed above, extract the firm name from the URL path or page content as best as possible.

Compare the firm from the bio link against the most recent role in the LinkedIn data. If they do not match, add a flag:

⚠️ Firm mismatch: Firm bio is [Firm from bio link] but LinkedIn shows most recent role at [Firm from LinkedIn]. Attorney may have recently moved and not updated LinkedIn, or LinkedIn data may be stale.

If the Firm Bio Link is empty or missing, skip the firm mismatch check entirely.

## Examples

Example 1 — Multiple firms, no partner promotion:
Associate, Cleary Gottlieb Steen & Hamilton (New York, May 2025 - Present)
Associate, Clifford Chance (New York, Oct 2022 - May 2025)
Associate, Clifford Chance (London, Aug 2019 - Jul 2021)
Trainee Lawyer, Clifford Chance (London, Aug 2017 - Aug 2019)

STABILITY: Stable — 2 firms in 8 years post-JD

Example 2 — Promotion to partner, lateral:
Partner, Morgan, Lewis & Bockius (Philadelphia, Oct 2020 - Present)
Associate, Morgan, Lewis & Bockius (Philadelphia, Oct 2006 - Oct 2020)
Associate, Cleary Gottlieb Steen & Hamilton (Oct 2003 - Aug 2006)

Partner since:
Oct 2020

STABILITY: Stable — 2 firms in 23 years post-JD

Example 3 — Flag, long tenure without title change:
Partner, Sidley Austin (New York, Aug 2022 - Present)
Associate, Jones Day (New York, Jun 2011 - Aug 2022)

⚠️ Flag: 11+ years at Jones Day with no promotion shown — likely made Partner before lateraling to Sidley. Press release search recommended.

STABILITY: Stable — 2 firms in 15 years post-JD

Example 4 — Firm mismatch flag:
Partner, Skadden, Arps, Slate, Meagher & Flom (New York, Jan 2023 - Present)
Associate, Skadden, Arps, Slate, Meagher & Flom (New York, Sep 2015 - Jan 2023)

Partner since:
Jan 2023

⚠️ Firm mismatch: Firm bio is Kirkland & Ellis but LinkedIn shows most recent role at Skadden, Arps, Slate, Meagher & Flom. Attorney may have recently moved and not updated LinkedIn, or LinkedIn data may be stale.

STABILITY: Stable — 1 firm in 11 years post-JD

---

IMPORTANT:
- The raw LinkedIn text will be messy — text is often duplicated, formatting is inconsistent. Parse through the noise to extract the correct firm, title, location, and dates.
- Accuracy is paramount. Dates and title progression must be correct.
- Do NOT fabricate any career history. Only use what is present in the LinkedIn data.
- If the LinkedIn data is empty, missing, or cannot be parsed, output: "No LinkedIn data available"
- If the Firm Bio Link is empty or missing, skip the firm mismatch check entirely.
- Respond with ONLY the formatted output and any flags. No extra commentary."""


def format_work_history(linkedin_data: str, firm_bio_link: str = "", model: str = "claude-sonnet-4-5-20251001") -> str:
    """
    Send LinkedIn data to Claude and return the formatted work history.
    """
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    user_content = f"**LinkedIn Data:**\n{linkedin_data}"
    if firm_bio_link and firm_bio_link.strip():
        user_content += f"\n\n**Firm Bio Link:** {firm_bio_link.strip()}"

    message = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return message.content[0].text


def run_single(args):
    """Single attorney mode."""
    result = format_work_history(args.linkedin, args.firm_bio_link or "", args.model)
    print(result)


def run_json_batch(args):
    """
    Batch mode — expects a JSON file with an array of objects:
    [
      {
        "name": "Jane Doe",
        "linkedin_data": "...",
        "firm_bio_link": "https://kirkland.com/..."   // optional
      },
      ...
    ]
    """
    with open(args.file, "r", encoding="utf-8") as f:
        records = json.load(f)

    results = []
    for i, rec in enumerate(records):
        name = rec.get("name", f"Record {i + 1}")
        linkedin_data = rec.get("linkedin_data", "")
        firm_bio_link = rec.get("firm_bio_link", "")

        print(f"Processing {name} ({i + 1}/{len(records)})...", file=sys.stderr)
        output = format_work_history(linkedin_data, firm_bio_link, args.model)
        results.append({"name": name, "formatted_work_history": output})
        print(f"{'=' * 60}")
        print(f"  {name}")
        print(f"{'=' * 60}")
        print(output)
        print()

    # Also write JSON output
    out_path = args.file.replace(".json", "_formatted.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nJSON output saved to: {out_path}", file=sys.stderr)


def run_csv_batch(args):
    """
    CSV batch mode — expects columns: name, linkedin_data, firm_bio_link (optional)
    Outputs a new CSV with an added 'formatted_work_history' column.
    """
    rows = []
    with open(args.csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    if "linkedin_data" not in fieldnames:
        print("ERROR: CSV must have a 'linkedin_data' column.", file=sys.stderr)
        sys.exit(1)

    out_fieldnames = list(fieldnames) + ["formatted_work_history"]
    out_path = args.csv.replace(".csv", "_formatted.csv")

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames)
        writer.writeheader()

        for i, row in enumerate(rows):
            name = row.get("name", f"Row {i + 1}")
            linkedin_data = row.get("linkedin_data", "")
            firm_bio_link = row.get("firm_bio_link", "")

            print(f"Processing {name} ({i + 1}/{len(rows)})...", file=sys.stderr)
            output = format_work_history(linkedin_data, firm_bio_link, args.model)
            row["formatted_work_history"] = output
            writer.writerow(row)

    print(f"\nCSV output saved to: {out_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Format attorney LinkedIn work history using Claude API."
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-5-20251001",
        help="Claude model to use (default: claude-sonnet-4-5-20251001)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--linkedin",
        type=str,
        help="Raw LinkedIn experience text for a single attorney",
    )
    group.add_argument(
        "--file",
        type=str,
        help="Path to a JSON file for batch processing",
    )
    group.add_argument(
        "--csv",
        type=str,
        help="Path to a CSV file for batch processing",
    )

    parser.add_argument(
        "--firm-bio-link",
        type=str,
        default="",
        help="Firm bio URL for cross-check (single mode only)",
    )

    args = parser.parse_args()

    # Verify API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set your API key first: export ANTHROPIC_API_KEY=sk-ant-...", file=sys.stderr)
        sys.exit(1)

    if args.linkedin:
        run_single(args)
    elif args.file:
        run_json_batch(args)
    elif args.csv:
        run_csv_batch(args)


if __name__ == "__main__":
    main()
