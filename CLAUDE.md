# python_scrape — Legal Professional LinkedIn Scraper

## What this project does

Batch pipeline that takes a CSV list of lawyers (name, firm, position, contact info) and:
1. Finds their LinkedIn profile via Google SERP search (Apify)
2. Scrapes the full LinkedIn profile (Apify)
3. Validates the profile matches the expected firm
4. Extracts and formats work history with intelligent flags
5. Extracts JD education info (law school, graduation year)
6. Outputs two CSVs: a full debug file and a clean results file

**Target use case:** Legal recruiting / due diligence on law firm personnel.

---

## Stack & Dependencies

- Python 3, `requests`, `python-dotenv`
- **Apify API** for two scrapers:
  - SERP: `scraperlink~google-search-results-serp-scraper`
  - LinkedIn profiles: `dev_fusion~Linkedin-Profile-Scraper`
- API token loaded from `.env` → `APIFY_API_TOKEN`

---

## File Map

| File | Role |
|------|------|
| `main.py` | Orchestrates the full pipeline, reads `input.csv`, writes `output.csv` + `results.csv` |
| `scraper.py` | Apify API wrappers: SERP search + LinkedIn profile scraper |
| `extractor.py` | Parses raw Apify JSON → work history entries, firm match check, JD extraction |
| `formatter.py` | Rule-based formatter: classifies roles, normalizes titles, adds intelligent flags |
| `input.csv` | Input: `name, site_page, position, email, url, locations_str` |
| `output.csv` | Full output with raw JSON (append mode, resumable) |
| `results.csv` | Clean summary for sharing/review |
| `debug_li.py` | Standalone test for LinkedIn scrape |
| `debug_serp.py` | Standalone test for SERP search |

---

## Data Flow

```
input.csv row
  → get_linkedin_url()        # SERP: "{name} {firm} {position} {location} LinkedIn"
  → scrape_linkedin_profile() # Full Apify LinkedIn scrape
  → extract_work_history()    # Parse experience_list from profile JSON
  → check_firm_match()        # Is the firm in any LinkedIn experience entry?
  → format_work_history()     # Rule-based: classify, normalize, flag
  → extract_jd_info()         # Find JD degree entry → school + year
  → write to output.csv + results.csv
```

---

## Work History Extraction (extractor.py)

Handles multiple Apify JSON key variants: `experience` / `experiences` / `experienceHistory`.

Each entry becomes:
```python
{
    "company": str,
    "title": str,
    "start_year": str,   # "2020" or ""
    "end_year": str      # "2024" or "Present"
}
```

---

## Work History Formatting (formatter.py)

**Role classification** (`_classify_role`):
- Skips: summers, interns, fellows, volunteers
- Clerkship: "law clerk" + federal court detection
- Law firm: industry = "law practice"/"legal services", or entity type (LLP, LLC, P.C.)
- In-house: counsel/attorney at non-law-firm company

**Title normalization** (`_normalize_title`):
- Partner ← "partner", "shareholder", "principal", "member"
- Senior Counsel ← "senior counsel"
- Counsel ← "counsel", "special counsel", "of counsel"
- Associate ← "associate", "attorney", "solicitor", "lawyer"
- Clerkship ← extracts judge name: "Law Clerk, Hon. {judge}, {court}"

**Flags generated:**
- `[!] Firm mismatch` — LinkedIn current firm ≠ firm from bio
- `[!] Gap` — 6+ month gap between roles
- `[!] Long tenure` — 10+ years without promotion (may be undisclosed Partner)
- `[!] Title jump` — Associate → Partner across firms (hidden Partner status)

---

## Output Columns

**output.csv** (full debug):
`name, site_page, position, email, url, locations_str, linkedin_url, jd_year, law_school, work_history (JSON), formatted_work_history, notes, raw_profile_json`

**results.csv** (clean summary):
`name, site_page, position, email, url, locations_str, status, linkedin_url, law_school, jd_year, work_history`

---

## Resume Logic

`main.py` counts rows already in `output.csv` and skips that many input rows — allowing interrupted runs to continue without re-processing.

---

## Known Issues / Improvement Areas

- **Work history extraction** is the most important feature and is actively being improved (see pending Leighton improvements below)
- Firm matching uses basic substring search — can produce false positives/negatives
- No retry logic for failed Apify calls
- Serial processing (~2 min/person); no parallelism
- `format_work_history()` is 100% rule-based, **not** AI-powered (misleading comment in main.py)

---

## Leighton's Work History Spec — Implemented in formatter.py

Leighton delivered `work_history_formatter.py` as a reference implementation using Claude API. All its rules are now implemented as **pure Python** in `formatter.py` — no API costs, no external dependencies beyond the standard library.

### What formatter.py implements (Leighton's full spec)

**Title normalization:**
- All Partner variants (Equity Partner, Shareholder, etc.) → `Partner`
- All Associate variants (M&A Associate, Senior Associate, Attorney, etc.) → `Associate`
- Special Counsel → `Counsel`, Senior Counsel kept as-is
- Trainee Lawyer kept as-is
- Clerkships → `Law Clerk, Hon. [Judge], [Court]`

**Inclusions / Exclusions:**
- Includes: law firm roles, in-house counsel, federal clerkships, secondments
- Excludes: summers, interns, fellows, volunteers, government (non-clerkship), non-legal roles, mini-pupillages

**Firm name cleanup:** Drops LLP, LLC, P.C., PLLC, etc.

**Partner since:** Multi-line block added at bottom if any Partner role found (earliest date)

**Stability tag:**
```
STABILITY: [Stable / Some movement / Unstable] — N firms in Y years post-JD
```
- Stable = 1-2 firms, or 3 firms each with 3+ year stints
- Some movement = 3-4 firms with at least one stint under 2 years
- Unstable = 5+ firms, or 2+ stints under 1 year

**Flags (⚠️ emoji):**
- Firm mismatch: bio link domain vs. LinkedIn current firm (30+ firm domain mappings)
- Gap: 6+ month gap between consecutive roles
- Long tenure: 10+ years at same firm with no promotion visible
- Title jump: Associate at Firm A → Partner at Firm B

**Multi-format date handling:** Handles all Apify actor variants:
- `"M-YYYY"` strings (dev_fusion actor)
- `{"year": 2023, "month": 10}` dicts (period.startedOn format)
- Plain year values

### work_history_formatter.py

This is Leighton's original standalone reference script. It uses Claude API and can be run independently for one-off formatting or testing. It is NOT used in the main pipeline — `formatter.py` handles everything in pure Python.

To use it standalone (requires `pip install anthropic` and `ANTHROPIC_API_KEY`):
```bash
python work_history_formatter.py --linkedin "paste raw linkedin text" --firm-bio-link "https://kirkland.com/..."
python work_history_formatter.py --file attorneys.json
python work_history_formatter.py --csv attorneys.csv
```

---

## How to Run

```bash
pip install -r requirements.txt
# Create .env with: APIFY_API_TOKEN=your_token_here
# Prepare input.csv with columns: name, site_page, position, email, url, locations_str
python main.py
```
