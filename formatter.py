import re
import json
from datetime import date
from urllib.parse import urlparse

CURRENT_YEAR = date.today().year
CURRENT_MONTH = date.today().month

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

JD_KEYWORDS = {"juris doctor", "j.d.", "jd", "doctor of jurisprudence"}
LAW_SCHOOL_KEYWORDS = {"law school", "school of law", "law center", "college of law"}

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
# Role classification
# ---------------------------------------------------------------------------

def _classify_role(entry: dict) -> str:
    title = (entry.get("title") or "").strip()
    company = (entry.get("companyName") or entry.get("company") or "").strip()
    industry = (entry.get("companyIndustry") or "").strip().lower()

    if _EXCLUDE_TITLE_RE.search(title):
        return "exclude"

    t_lower = title.lower()

    # Federal clerkship — must come before government check
    if ("law clerk" in t_lower or "judicial clerk" in t_lower) and _FEDERAL_COURT_RE.search(company):
        return "clerkship"

    # Government — exclude except clerkships above
    if industry in _GOVERNMENT_INDUSTRIES or _GOVERNMENT_NAME_RE.search(company):
        return "government"

    # Secondment — classify by destination company type
    if "secondment" in t_lower or "secondee" in t_lower:
        if industry in ("law practice", "legal services") or _ENTITY_RE.search(company):
            return "law_firm"
        return "inhouse"

    # Law firm
    if industry in ("law practice", "legal services"):
        return "law_firm"
    if _ENTITY_RE.search(company) or re.search(r'\blaw\s+(firm|group|offices?)\b', company, re.IGNORECASE):
        return "law_firm"

    # In-house legal role at non-law-firm company
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

    return title


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _clean_firm_name(name: str) -> str:
    return _ENTITY_RE.sub("", name).strip().rstrip(",").strip()


def _parse_month_year(raw) -> tuple[int, int] | None:
    """
    Parse a raw date value from any Apify actor format to (month, year).

    Handles:
      - "M-YYYY" strings like "10-2023"   (dev_fusion actor)
      - {"year": 2023, "month": 10} dicts (period.startedOn format)
      - Plain year strings or ints
    """
    if not raw:
        return None
    if isinstance(raw, dict):
        yr = raw.get("year")
        mo = raw.get("month", 1)
        return (int(mo), int(yr)) if yr else None
    s = str(raw).strip()
    m = re.match(r'^(\d{1,2})-(\d{4})$', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    yr = re.search(r'\b(19|20)\d{2}\b', s)
    return (1, int(yr.group(0))) if yr else None


def _get_date(entry: dict, field_prefix: str) -> tuple[int, int] | None:
    """
    Try multiple Apify actor field variants for start or end date.
    field_prefix: "start" or "end"
    """
    if field_prefix == "start":
        raw = (
            entry.get("jobStartedOn")
            or entry.get("startDate") or entry.get("start_date")
            or entry.get("startYear")
        )
        if not raw:
            period = entry.get("period") or {}
            raw = period.get("startedOn")
    else:
        raw = (
            entry.get("jobEndedOn")
            or entry.get("endDate") or entry.get("end_date")
            or entry.get("endYear")
        )
        if not raw:
            period = entry.get("period") or {}
            raw = period.get("endedOn")

    return _parse_month_year(raw)


def _format_my(my: tuple[int, int] | None, still_working: bool = False) -> str:
    if still_working:
        return "Present"
    if not my:
        return ""
    month, year = my
    label = MONTH_MAP.get(month, "")
    return f"{label} {year}".strip() if label else str(year)


def _format_location(location: str) -> str:
    if not location:
        return ""
    city = location.split(",")[0].strip()
    if re.match(r'^\d+', city) and "," in location:
        city = location.split(",")[1].strip()
    city = re.sub(r'^Greater\s+', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'\s+(?:City\s+)?(?:Metropolitan|Metro)\s+Area$', '', city, flags=re.IGNORECASE).strip()
    city = re.sub(r'\s*[-–]\s*.+?\s+Area$', '', city).strip()
    city = re.sub(r'\s+Area$', '', city, flags=re.IGNORECASE).strip()
    return city


def _firm_from_bio_link(bio_link: str) -> tuple[str | None, str | None]:
    if not bio_link:
        return None, None
    try:
        domain = urlparse(bio_link).netloc.lower().lstrip("www.")
        return FIRM_DOMAINS.get(domain), domain
    except Exception:
        return None, None


def _months_between(earlier: tuple[int, int], later: tuple[int, int]) -> int:
    return (later[1] - earlier[1]) * 12 + (later[0] - earlier[0])


# ---------------------------------------------------------------------------
# JD year extraction (used for stability tag)
# ---------------------------------------------------------------------------

def _extract_jd_year(profile: dict) -> int | None:
    education_list = (
        profile.get("education")
        or profile.get("educations")
        or profile.get("educationHistory")
        or []
    )
    for entry in education_list:
        degree = (
            entry.get("subtitle") or entry.get("degree")
            or entry.get("degreeName") or entry.get("fieldOfStudy") or ""
        ).lower()
        school = (
            entry.get("title") or entry.get("schoolName") or entry.get("school") or ""
        ).lower()

        is_jd = any(kw in degree for kw in JD_KEYWORDS)
        is_law_school = not degree and any(kw in school for kw in LAW_SCHOOL_KEYWORDS)

        if is_jd or is_law_school:
            period = entry.get("period") or {}
            ended_on = period.get("endedOn") or {}
            yr = (
                ended_on.get("year")
                or entry.get("endYear") or entry.get("end_year")
                or entry.get("graduationYear")
            )
            return int(yr) if yr else None
    return None


# ---------------------------------------------------------------------------
# Stability tag
# ---------------------------------------------------------------------------

def _compute_stability(roles: list, jd_year: int | None) -> str:
    """
    STABILITY: [Stable / Some movement / Unstable] — N firms in Y years post-JD

    Stable        = 1-2 firms, or 3 firms each with 3+ year stints
    Some movement = 3-4 firms with at least one stint under 2 years
    Unstable      = 5+ firms, OR 2+ stints under 1 year
    """
    firm_windows: dict[str, dict] = {}
    for r in roles:
        firm = r["firm"]
        if not firm:
            continue
        key = firm.lower()
        start = r["start_my"]
        # Use current date as end for still-working roles
        end = r["end_my"] or ((CURRENT_MONTH, CURRENT_YEAR) if r["still_working"] else None)
        if key not in firm_windows:
            firm_windows[key] = {"name": firm, "starts": [], "ends": []}
        if start:
            firm_windows[key]["starts"].append(start)
        if end:
            firm_windows[key]["ends"].append(end)

    n_firms = len(firm_windows)
    if n_firms == 0:
        return ""

    stint_years: list[float] = []
    for data in firm_windows.values():
        if data["starts"] and data["ends"]:
            earliest = min(data["starts"], key=lambda my: my[1] * 12 + my[0])
            latest = max(data["ends"], key=lambda my: my[1] * 12 + my[0])
            stint_years.append(_months_between(earliest, latest) / 12)

    short_stints = sum(1 for y in stint_years if y < 1)

    if n_firms <= 2:
        tag = "Stable"
    elif n_firms == 3 and all(y >= 3 for y in stint_years):
        tag = "Stable"
    elif n_firms >= 5 or short_stints >= 2:
        tag = "Unstable"
    elif n_firms <= 4 and any(y < 2 for y in stint_years):
        tag = "Some movement"
    else:
        tag = "Some movement"

    plural = "s" if n_firms != 1 else ""
    if jd_year:
        years_post_jd = CURRENT_YEAR - jd_year
        return f"STABILITY: {tag} — {n_firms} firm{plural} in {years_post_jd} years post-JD"
    return f"STABILITY: {tag} — {n_firms} firm{plural}"


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

    jd_year = _extract_jd_year(profile)

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

        # Clerkship title already embeds the court name — don't repeat it as firm
        if role_type == "clerkship":
            firm = ""
        elif role_type == "inhouse":
            firm = company_raw
        else:
            firm = _clean_firm_name(company_raw)

        city = _format_location(entry.get("jobLocation") or "")
        still_working = bool(entry.get("jobStillWorking", False))

        start_my = _get_date(entry, "start")
        end_my = None if still_working else _get_date(entry, "end")

        start_str = _format_my(start_my)
        end_str = _format_my(end_my, still_working)

        if start_str and end_str:
            date_range = f"{start_str} - {end_str}"
        elif start_str or end_str:
            date_range = start_str or end_str
        else:
            date_range = ""

        if city and date_range:
            paren = f"({city}, {date_range})"
        elif date_range:
            paren = f"({date_range})"
        elif city:
            paren = f"({city})"
        else:
            paren = ""

        line = f"{title}, {firm} {paren}".strip() if firm else f"{title} {paren}".strip()

        roles.append({
            "line": line,
            "title": title,
            "firm": firm,
            "role_type": role_type,
            "still_working": still_working,
            "start_my": start_my,
            "end_my": end_my,
        })

    if not roles:
        return "No LinkedIn data available"

    lines = [r["line"] for r in roles]

    # Partner since — earliest Partner role (roles is newest-first, reversed = oldest-first)
    earliest_partner = next((r for r in reversed(roles) if r["title"] == "Partner"), None)
    if earliest_partner and earliest_partner["start_my"]:
        ps = _format_my(earliest_partner["start_my"])
        if ps:
            lines.append(f"\nPartner since:\n{ps}")

    # Stability tag
    stability = _compute_stability(roles, jd_year)
    if stability:
        lines.append(f"\n{stability}")

    # --- Flags ---
    flags = []

    # Firm mismatch
    bio_firm, _bio_domain = _firm_from_bio_link(firm_bio_link)
    if bio_firm and roles:
        current_firm = roles[0]["firm"]
        if current_firm and bio_firm.lower() not in current_firm.lower() and current_firm.lower() not in bio_firm.lower():
            flags.append(
                f"⚠️ Firm mismatch: Firm bio is {bio_firm} but LinkedIn shows most recent "
                f"role at {current_firm}. Attorney may have recently moved and not updated "
                f"LinkedIn, or LinkedIn data may be stale."
            )

    # Gap — 6+ months between end of older role and start of newer role
    # roles is newest-first, so roles[i] is newer, roles[i+1] is older
    for i in range(len(roles) - 1):
        newer = roles[i]
        older = roles[i + 1]
        if older["still_working"]:
            continue
        older_end = older["end_my"]
        newer_start = newer["start_my"]
        if older_end and newer_start:
            gap_months = _months_between(older_end, newer_start)
            if gap_months >= 6:
                curr_label = newer["firm"] or newer["title"]
                prev_label = older["firm"] or older["title"]
                flags.append(
                    f"⚠️ Gap: ~{gap_months}-month gap between "
                    f"{prev_label} and {curr_label}."
                )

    # Long tenure — 10+ years at same firm with no title change shown
    firm_groups: dict[str, list] = {}
    for r in roles:
        if not r["firm"]:
            continue
        firm_groups.setdefault(r["firm"].lower(), []).append(r)

    for _key, group in firm_groups.items():
        firm_name = group[0]["firm"]
        titles_seen = {r["title"] for r in group}
        if "Partner" in titles_seen:
            continue  # promotion visible, no flag needed
        if len(titles_seen) > 1:
            continue  # multiple titles = promotion chain visible
        starts = [r["start_my"] for r in group if r["start_my"]]
        ends = [
            r["end_my"] or ((CURRENT_MONTH, CURRENT_YEAR) if r["still_working"] else None)
            for r in group
        ]
        ends = [e for e in ends if e]
        if starts and ends:
            earliest = min(starts, key=lambda my: my[1] * 12 + my[0])
            latest = max(ends, key=lambda my: my[1] * 12 + my[0])
            months = _months_between(earliest, latest)
            if months >= 120:
                years = months // 12
                flags.append(
                    f"⚠️ Long tenure: {years}+ years at {firm_name} with no promotion "
                    f"shown — likely made Partner before lateraling. Press release search recommended."
                )

    # Title jump — Associate at Firm A → Partner at Firm B with no Partner history at A
    for i in range(len(roles) - 1):
        if roles[i]["title"] == "Partner" and roles[i + 1]["title"] == "Associate":
            prev_firm = roles[i + 1]["firm"]
            curr_firm = roles[i]["firm"]
            if prev_firm and curr_firm and prev_firm.lower() != curr_firm.lower():
                had_partner_at_prev = any(
                    r["title"] == "Partner" and r["firm"].lower() == prev_firm.lower()
                    for r in roles
                )
                if not had_partner_at_prev:
                    flags.append(
                        f"⚠️ Title jump: Associate at {prev_firm} → Partner at "
                        f"{curr_firm} — may have made Partner at {prev_firm} first."
                    )

    if flags:
        lines.append("")
        lines.extend(flags)

    return "\n".join(lines)
