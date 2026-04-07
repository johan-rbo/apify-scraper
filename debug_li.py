import json
import requests
import os
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN")
APIFY_BASE = "https://api.apify.com/v2"
LI_ACTOR = "dev_fusion~Linkedin-Profile-Scraper"

url = f"{APIFY_BASE}/acts/{LI_ACTOR}/run-sync-get-dataset-items"
params = {"token": APIFY_TOKEN}
input_data = {
    "profileUrls": ["https://www.linkedin.com/in/jennilevy"]
}

print("Calling Apify LinkedIn scraper...")
response = requests.post(url, json=input_data, params=params, timeout=120)
print(f"Status code: {response.status_code}")
print("\nRaw response:")
print(json.dumps(response.json(), indent=2))
