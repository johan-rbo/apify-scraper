import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_BASE = "https://api.apify.com/v2"

SERP_ACTOR = "scraperlink~google-search-results-serp-scraper"
LI_ACTOR = "dev_fusion~Linkedin-Profile-Scraper"


def _run_actor(actor_id: str, input_data: dict) -> list:
    """Run an Apify actor synchronously and return the dataset items."""
    url = f"{APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items"
    params = {"token": APIFY_TOKEN}
    response = requests.post(url, json=input_data, params=params, timeout=120)
    response.raise_for_status()
    return response.json()


def get_linkedin_url(name: str, company: str, position: str) -> str | None:
    """
    Use Apify SERP scraper to find the LinkedIn profile URL for a person.
    Returns the first linkedin.com/in/ URL found, or None.
    """
    keyword = f"{name} {company} {position} LinkedIn"
    input_data = {
        "country": "US",
        "include_merged": True,
        "keyword": keyword,
        "limit": "10",
        "page": 1,
        "proxy_location": "us",
        "start": 1,
    }

    print(f"  [SERP] Searching: {keyword}")
    results = _run_actor(SERP_ACTOR, input_data)

    for item in results:
        for result in item.get("results", []):
            link = result.get("url", "")
            # Must be a real profile URL, not posts/directories
            if "linkedin.com/in/" in link:
                print(f"  [SERP] Found LinkedIn URL: {link}")
                return link

    print("  [SERP] No LinkedIn URL found.")
    return None


def scrape_linkedin_profile(linkedin_url: str) -> dict | None:
    """
    Use Apify LinkedIn Profile Scraper to get full profile data.
    Returns the raw profile dict, or None if not found.
    """
    input_data = {
        "profileUrls": [linkedin_url]
    }

    print(f"  [LI] Scraping profile: {linkedin_url}")
    results = _run_actor(LI_ACTOR, input_data)

    if results:
        return results[0]

    print("  [LI] No profile data returned.")
    return None
