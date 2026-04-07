JD_KEYWORDS = {"juris doctor", "j.d.", "jd", "doctor of jurisprudence"}


def _is_jd(degree: str) -> bool:
    if not degree:
        return False
    normalized = degree.lower().strip()
    return any(kw in normalized for kw in JD_KEYWORDS)


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

        if _is_jd(degree):
            law_school = (
                entry.get("title")          # dev_fusion actor uses "title" for school name
                or entry.get("schoolName")
                or entry.get("school")
                or entry.get("institutionName")
            )
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
