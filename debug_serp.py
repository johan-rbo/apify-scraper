import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_BASE = "https://api.apify.com/v2"
SERP_ACTOR = "scraperlink~google-search-results-serp-scraper"

url = f"{APIFY_BASE}/acts/{SERP_ACTOR}/run-sync-get-dataset-items"
params = {"token": APIFY_TOKEN}
input_data = {
    "country": "US",
    "include_merged": True,
    "keyword": "Jennifer Levy Cleary Gottlieb Senior Discovery Attorney LinkedIn",
    "limit": "10",
    "page": 1,
    "proxy_location": "us",
    "start": 1,
}

print("Calling Apify SERP actor...")
response = requests.post(url, json=input_data, params=params, timeout=120)
print(f"Status code: {response.status_code}")
print("\nRaw response:")
print(json.dumps(response.json(), indent=2))
