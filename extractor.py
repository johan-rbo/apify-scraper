JD_KEYWORDS = {"juris doctor", "j.d.", "jd", "doctor of jurisprudence"}
LAW_SCHOOL_KEYWORDS = {"law school", "school of law", "law center", "college of law"}


def check_firm_match(profile: dict, site_page: str) -> bool:
    """
    Returns True if the LinkedIn profile contains the firm (site_page) in any
    experience entry or the top-level companyName.
    Matching is case-insensitive and partial (site_page contained in company name).
    """
    if not profile or not site_page:
        return False

    firm_lower = site_page.lower().strip()

    # Check top-level companyName first (current job)
    top_company = (profile.get("companyName") or "").lower()
    if firm_lower in top_company:
        return True

    # Check all experience entries
    experience_list = (
        profile.get("experience")
        or profile.get("experiences")
        or profile.get("experienceHistory")
        or []
    )
    for entry in experience_list:
        company = (
            entry.get("companyName")
            or entry.get("company")
            or entry.get("subtitle")
            or ""
        ).lower()
        if firm_lower in company:
            return True

    # Also check headline as a fallback
    headline = (profile.get("headline") or "").lower()
    if firm_lower in headline:
        return True

    return False


def _is_jd(degree: str) -> bool:
    if not degree:
        return False
    normalized = degree.lower().strip()
    return any(kw in normalized for kw in JD_KEYWORDS)


def _is_law_school(school_name: str) -> bool:
    if not school_name:
        return False
    normalized = school_name.lower().strip()
    return any(kw in normalized for kw in LAW_SCHOOL_KEYWORDS)


def extract_jd_info(profile: dict) -> tuple[str | None, str | None]:
    """
    Parse the Apify LinkedIn profile JSON and extract:
      - law_school: name of the school where the JD was obtained
      - jd_year: graduation year (end year) of the JD program

    Returns (law_school, jd_year) — either can be None if not found.
    """
    if not profile:
        return None, None

    # Education can live under different keys depending on the actor version
    education_list = (
        profile.get("education")
        or profile.get("educations")
        or profile.get("educationHistory")
        or []
    )

    law_school = None
    jd_year = None

    for entry in education_list:
        degree = (
            entry.get("subtitle")       # dev_fusion actor uses "subtitle"
            or entry.get("degree")
            or entry.get("degreeName")
            or entry.get("fieldOfStudy")
            or ""
        )
        school_name = (
            entry.get("title")
            or entry.get("schoolName")
            or entry.get("school")
            or entry.get("institutionName")
            or ""
        )

        if _is_jd(degree) or (not degree and _is_law_school(school_name)):
            law_school = school_name or None
            # dev_fusion actor: period.endedOn.year
            period = entry.get("period") or {}
            ended_on = period.get("endedOn") or {}
            end_year = (
                ended_on.get("year")
                or entry.get("endYear")
                or entry.get("end_year")
                or entry.get("graduationYear")
                or _parse_year_from_date(entry.get("endDate") or entry.get("end_date"))
            )
            jd_year = str(end_year) if end_year else None
            break  # take the first JD match

    return law_school, jd_year


def _parse_year_from_date(date_value) -> str | None:
    """Extract a 4-digit year from strings like '2005-01-01' or dicts like {'year': 2005}."""
    if not date_value:
        return None
    if isinstance(date_value, dict):
        return str(date_value.get("year")) if date_value.get("year") else None
    date_str = str(date_value)
    # grab the first 4-digit sequence
    import re
    match = re.search(r"\b(19|20)\d{2}\b", date_str)
    return match.group(0) if match else None
