import os
import requests
from dotenv import load_dotenv

load_dotenv()

ZENEX_API_KEY = os.getenv("ZENEX_API_KEY")
ZENEX_CORE_URL = os.getenv("ZENEX_BASE_URL", "https://api.zenexnetwork.com")
ZENEX_WEB_URL = os.getenv("ZENEX_WEB_BASE_URL", "https://www.zenexnetwork.com")

HEADERS = {
    "mapikey": ZENEX_API_KEY,
    "Content-Type": "application/json"
}

def provision_virtual_number(range_prefix: str, is_national: bool = False, remove_plus: bool = False) -> dict:
    """Provisions a temporary or permanent virtual number."""
    url = f"{ZENEX_CORE_URL}/v1/getnum"
    payload = {
        "range": range_prefix,
        "is_national": is_national,
        "remove_plus": remove_plus
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        return response.json()
    except Exception as e:
        return {"meta": {"code": 500, "status": "error"}, "message": str(e)}

def fetch_sms_payloads() -> dict:
    """Polls the Zenex Core Engine to fetch incoming SMS payloads."""
    url = f"{ZENEX_CORE_URL}/v1/numsuccess/info"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        return response.json()
    except Exception as e:
        return {"meta": {"code": 500, "status": "error"}, "message": str(e)}

def fetch_active_ranges() -> dict:
    """Exports the global live routing matrix."""
    url = f"{ZENEX_CORE_URL}/v1/active-ranges"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}

def fetch_global_broadcast() -> dict:
    """Fetches the global live feed of recent successful OTPs across the ZENEX network."""
    url = f"{ZENEX_WEB_URL}/api/v1/global-broadcast"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}