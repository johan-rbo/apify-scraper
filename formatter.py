import re
import json
from urllib.parse import urlparse
from datetime import date

CURRENT_YEAR = date.today().year

MONTH_MAP = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

FIRM_DOMAINS = {
    "kirkland.com": "Kirkland & Ellis",
    "lw.com": "Latham & Watkins",
    "skadden.com": "Skadden, Arps, Slate, Meagher & Flom",
    "weil.com": "Weil, Gotshal & Manges",
    "sullcrom.com": "Sullivan & Cromwell",
    "davispolk.com": "Davis Polk & Wardwell",
    "cravath.com": "Cravath, Swaine & Moore",
    "sidley.com": "Sidley Austin",
    "gibsondunn.com": "Gibson, Dunn & Crutcher",
    "jonesday.com": "Jones Day",
    "velaw.com": "Vinson & Elkins",
    "bracewell.com": "Bracewell",
    "haynesboone.com": "Haynes and Boone",
    "akingump.com": "Akin Gump Strauss Hauer & Feld",
    "wlrk.com": "Wachtell, Lipton, Rosen & Katz",
    "paulweiss.com": "Paul, Weiss, Rifkind, Wharton & Garrison",
    "clearygottlieb.com": "Cleary Gottlieb Steen & Hamilton",
    "milbank.com": "Milbank",
    "shearman.com": "Shearman & Sterling",
    "whitecase.com": "White & Case",
    "morganlewis.com": "Morgan, Lewis & Bockius",
    "klgates.com": "K&L Gates",
    "huntonak.com": "Hunton Andrews Kurth",
    "bakerbotts.com": "Baker Botts",
    "lockelord.com": "Locke Lord",
    "winston.com": "Winston & Strawn",
    "porterhedges.com": "Porter Hedges",
    "tklaw.com": "Thompson & Knight",
    "nortonrosefulbright.com": "Norton Rose Fulbright",
}

_ENTITY_RE = re.compile(
    r'\s*\b(LLP|LLC|P\.C\.|L\.L\.P\.|L\.L\.C\.|PLLC|P\.L\.L\.C\.|Ltd\.?|Inc\.?)\b\.?',
    re.IGNORECASE,
)

_FEDERAL_COURT_RE = re.compile(
    r'\bu\.s\.\s+(district|circuit|court|supreme|bankruptcy)\b'
    r'|\bfederal\s+(district\s+)?court\b'
    r'|\bcourt\s+of\s+appeals\b'
    r'|\b\d+(?:st|nd|rd|th)\s+circuit\b'
    r'|\bsupreme\s+court\s+of\s+the\s+u\.s\b'
    r'|\bu\.s\.\s+court\b',
    re.IGNORECASE,
)

_GOVERNMENT_INDUSTRIES = {
    "law enforcement", "government administration", "public policy",
    "political organization", "military", "public safety",
}

_GOVERNMENT_NAME_RE = re.compile(
    r'\bu\.s\.\s+department\b|\bdepartment\s+of\b|\bwhite\s+house\b'
    r'|\bnational\s+security\s+council\b|\battorney\s+general\b'
    r'|\bdistrict\s+attorney\b|\bpublic\s+defender\b'
    r'|\bcity\s+of\b|\bstate\s+of\b|\boffice\s+of\b'
    r'|\bfederal\s+bureau\b|\bcommission\b',
    re.IGNORECASE,
)

_EXCLUDE_TITLE_RE = re.compile(
    r'\bsummer\s+associate\b|\bintern(ship)?\b|\bextern(ship)?\b'
    r'|\bfellow(ship)?\b|\bvolunteer\b|\bstudent\b|\bmini.?pupillage\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify_role(entry: dict) -> str:
    title = (entry.get("title") or "").strip()
    company = (entry.get("companyName") or entry.get("company") or "").strip()
    industry = (entry.get("companyIndustry") or "").strip().lower()

    if _EXCLUDE_TITLE_RE.search(title):
        return "exclude"

    # Federal clerkship (check before government — courts are gov but we keep them)
    t_lower = title.lower()
    if ("law clerk" in t_lower or "judicial clerk" in t_lower) and _FEDERAL_COURT_RE.search(company):
        return "clerkship"

    # Government (exclude, except clerkships above)
    if industry in _GOVERNMENT_INDUSTRIES or _GOVERNMENT_NAME_RE.search(company):
        return "government"

    # Law firm
    if industry == "law practice" or industry == "legal services":
        return "law_firm"
    if _ENTITY_RE.search(company) or re.search(r'\blaw\s+(firm|group|offices?)\b', company, re.IGNORECASE):
        return "law_firm"

    # In-house legal role at a non-law-firm company
    if re.search(r'\bcounsel\b|\battorney\b', t_lower):
        return "inhouse"
    if re.search(r'\blegal\b', t_lower) and re.search(
        r'\b(vice\s+president|vp|director|officer|head|manager)\b', t_lower
    ):
        return "inhouse"

    return "exclude"


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------

def _normalize_title(title: str, role_type: str, company: str) -> str:
    t = title.lower()

    if role_type == "clerkship":
        judge = re.search(
            r'(?:to|for)\s+((?:Justice|Judge|Hon\.?)\s+[^,\n]+)',
            title, re.IGNORECASE,
        )
        if judge:
            judge_name = re.sub(r'^(?:Justice|Judge)\s+', '', judge.group(1), flags=re.IGNORECASE).strip()
            return f"Law Clerk, Hon. {judge_name}, {company}"
        return f"Law Clerk, {company}"

    if "special counsel" in t:
        return "Counsel"
    if "senior counsel" in t:
        return "Senior Counsel"
    if "of counsel" in t:
        return "Counsel"
    if "counsel" in t:
        return "Counsel"
    if re.search(r'\btrainee\b', t) and re.search(r'\b(lawyer|solicitor)\b', t):
        return "Trainee Lawyer"
    if re.search(r'\b(partner|shareholder|principal|member)\b', t) and "associate" not in t:
        return "Partner"
    if re.search(r'\b(associate|attorney|solicitor|senior attorney|senior associate|lawyer)\b', t):
        return "Associate"

    return title  # keep as-is if no rule matches (e.g. in-house VP titles)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _clean_firm_name(name: str) -> str:
    cleaned = _ENTITY_RE.sub("", name).strip().rstrip(",").strip()
    return cleaned


def _format_date(date_str, still_working: bool = False) -> str:
    if still_working:
        return "Present"
    if not date_str:
        return ""
    s = str(date_str).strip()
    m = re.match(r'^(\d{1,2})-(\d{4})$', s)
    if m:
        month, year = int(m.group(1)), m.group(2)
        return f"{MONTH_MAP.get(month, '')} {year}".strip()
    yr = re.search(r'\b(19|20)\d{2}\b', s)
    return yr.group(0) if yr else ""


def _format_location(location: str) -> str:
    if not location:
        return ""
    city = location.split(",")[0].strip()
    # Skip street addresses — use next segment
    if re.match(r'^\d+', city) and "," in location:
        city = location.split(",")[1].strip()
    city = re.sub(r'^Greater\s+', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'\s+(?:City\s+)?(?:Metropolitan|Metro)\s+Area$', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'\s*[-–]\s*.+?\s+Area$', '', city).strip()
    city = re.sub(r'\s+Area$', '', city, flags=re.IGNORECASE).strip()
    return city


def _parse_month_year(date_str, still_working: bool = False):
    """Returns (month, year) as ints, or None."""
    if still_working or not date_str:
        return None
    s = str(date_str).strip()
    m = re.match(r'^(\d{1,2})-(\d{4})$', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    yr = re.search(r'\b(19|20)\d{2}\b', s)
    return (1, int(yr.group(0))) if yr else None


def _parse_year_int(date_str, still_working: bool = False) -> int | None:
    if still_working or not date_str:
        return None
    s = str(date_str).strip()
    m = re.match(r'^(\d{1,2})-(\d{4})$', s)
    if m:
        return int(m.group(2))
    yr = re.search(r'\b(19|20)\d{2}\b', s)
    return int(yr.group(0)) if yr else None


def _firm_from_bio_link(bio_link: str) -> tuple[str | None, str | None]:
    """Returns (firm_name, domain) from bio link, or (None, None)."""
    if not bio_link:
        return None, None
    try:
        domain = urlparse(bio_link).netloc.lower().lstrip("www.")
        return FIRM_DOMAINS.get(domain), domain
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def format_work_history(raw_profile_json: str, firm_bio_link: str = "") -> str:
    if not raw_profile_json:
        return "No LinkedIn data available"

    try:
        profile = json.loads(raw_profile_json)
    except (json.JSONDecodeError, TypeError):
        return "No LinkedIn data available"

    experience_list = (
        profile.get("experiences")
        or profile.get("experience")
        or profile.get("experienceHistory")
        or []
    )

    if not experience_list:
        return "No LinkedIn data available"

    # Build structured role list
    roles = []
    for entry in experience_list:
        role_type = _classify_role(entry)
        if role_type in ("government", "exclude"):
            continue

        title_raw = (entry.get("title") or "").strip()
        company_raw = (entry.get("companyName") or entry.get("company") or "").strip()
        if not title_raw and not company_raw:
            continue

        title = _normalize_title(title_raw, role_type, company_raw)
        # Clerkship titles already embed the court name — don't repeat it as firm
        if role_type == "clerkship":
            firm = ""
        elif role_type == "inhouse":
            firm = company_raw
        else:
            firm = _clean_firm_name(company_raw)
        city = _format_location(entry.get("jobLocation") or "")
        started = entry.get("jobStartedOn")
        ended = entry.get("jobEndedOn")
        still_working = entry.get("jobStillWorking", False)

        start_str = _format_date(started)
        end_str = _format_date(ended, still_working)
        date_range = f"{start_str} - {end_str}".strip(" -")

        if city and date_range:
            paren = f"({city}, {date_range})"
        elif date_range:
            paren = f"({date_range})"
        elif city:
            paren = f"({city})"
        else:
            paren = ""

        if firm:
            line = f"{title}, {firm} {paren}".strip()
        else:
            line = f"{title} {paren}".strip()

        roles.append({
            "line": line,
            "title": title,
            "firm": firm,
            "started": started,
            "ended": ended,
            "still_working": still_working,
        })

    if not roles:
        return "No LinkedIn data available"

    lines = [r["line"] for r in roles]

    # Partner since — earliest date any Partner role started
    partner_since = None
    for r in reversed(roles):  # reversed = oldest first (roles list is newest-first)
        if r["title"] == "Partner":
            ps = _format_date(r["started"])
            if ps:
                partner_since = ps
                break
    if partner_since:
        lines.append(f"\nPartner since: {partner_since}")

    # --- Flags ---
    flags = []

    # Firm mismatch
    bio_firm, bio_domain = _firm_from_bio_link(firm_bio_link)
    if bio_firm and roles:
        current_firm = roles[0]["firm"]
        if bio_firm.lower() not in current_firm.lower() and current_firm.lower() not in bio_firm.lower():
            flags.append(
                f"[!] Firm mismatch: Firm bio is {bio_firm} ({bio_domain}) but LinkedIn shows "
                f"most recent role at {current_firm}. Attorney may have recently moved and not "
                f"updated LinkedIn, or LinkedIn data may be stale."
            )

    # Gap (6+ months between consecutive roles)
    for i in range(len(roles) - 1):
        curr_end = _parse_month_year(roles[i]["ended"], roles[i]["still_working"])
        next_start = _parse_month_year(roles[i + 1]["started"])
        if curr_end and next_start:
            gap_months = (next_start[1] - curr_end[1]) * 12 + (next_start[0] - curr_end[0])
            if gap_months >= 6:
                flags.append(
                    f"[!] Gap: ~{gap_months}-month gap between "
                    f"{roles[i + 1]['firm']} and {roles[i]['firm']}."
                )

    # Long tenure (10+ years, single title at a firm)
    firm_title_groups: dict[tuple, list] = {}
    for r in roles:
        key = (r["firm"], r["title"])
        firm_title_groups.setdefault(key, []).append(r)

    for (firm, title), group in firm_title_groups.items():
        if len(group) == 1:
            r = group[0]
            start_yr = _parse_year_int(r["started"])
            end_yr = _parse_year_int(r["ended"], r["still_working"]) or CURRENT_YEAR
            if start_yr and (end_yr - start_yr) >= 10:
                flags.append(
                    f"[!] Long tenure: {end_yr - start_yr}+ years at {firm} with no promotion "
                    f"shown - likely made Partner before lateraling. Press release search recommended."
                )

    # Title jump (Associate at Firm A → Partner at Firm B, no partner history at A)
    for i in range(len(roles) - 1):
        if roles[i]["title"] == "Partner" and roles[i + 1]["title"] == "Associate":
            prev_firm = roles[i + 1]["firm"]
            curr_firm = roles[i]["firm"]
            if prev_firm != curr_firm:
                had_partner_at_prev = any(
                    r["title"] == "Partner" and r["firm"] == prev_firm for r in roles
                )
                if not had_partner_at_prev:
                    flags.append(
                        f"[!] Title jump: Associate at {prev_firm} -> Partner at {curr_firm} - "
                        f"may have made Partner at {prev_firm} first."
                    )

    if flags:
        lines.append("")
        lines.extend(flags)

    return "\n".join(lines)
