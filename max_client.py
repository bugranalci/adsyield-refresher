"""AppLovin MAX Management API client.

Ad unit listeleme, okuma ve güncelleme işlemleri.
"""
import time
import requests
from datetime import datetime
from typing import Optional, Tuple

BASE_URL = "https://o.applovin.com/mediation/v1"
MAX_RATE_LIMIT_RETRIES = 5
DEFAULT_TIMEOUT = 30
RATE_LIMIT_WAIT_SECONDS = 60


def _headers(management_key: str) -> dict:
    return {
        "Api-Key": management_key,
        "Content-Type": "application/json",
    }


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [MAX] {msg}")


def list_all_ad_units(management_key: str) -> list:
    """MAX API'den tüm ad unit'leri pagination ile çek."""
    all_units = []
    limit = 100
    offset = 0
    headers = _headers(management_key)
    rate_retries = 0

    while True:
        url = f"{BASE_URL}/ad_units?fields=ad_network_settings&limit={limit}&offset={offset}"
        try:
            r = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
            if r.status_code == 429:
                rate_retries += 1
                if rate_retries > MAX_RATE_LIMIT_RETRIES:
                    _log(f"Rate limit {MAX_RATE_LIMIT_RETRIES} kez asildi, durduruluyor")
                    break
                _log(f"Rate limit — {RATE_LIMIT_WAIT_SECONDS}s bekleniyor... ({rate_retries}/{MAX_RATE_LIMIT_RETRIES})")
                time.sleep(RATE_LIMIT_WAIT_SECONDS)
                continue
            rate_retries = 0
            if r.status_code != 200:
                _log(f"HATA: {r.status_code} — {r.text[:200]}")
                break
            data = r.json()
            if not data:
                break
            all_units.extend(data)
            _log(f"{len(all_units)} ad unit cekildi...")
            if len(data) < limit:
                break
            offset += limit
            time.sleep(0.2)
        except requests.exceptions.Timeout:
            _log(f"Timeout ({DEFAULT_TIMEOUT}s)")
            break
        except Exception as e:
            _log(f"HATA: {e}")
            break
    return all_units


def get_ad_unit(management_key: str, ad_unit_id: str) -> Optional[dict]:
    """Tekil ad unit detayı."""
    url = f"{BASE_URL}/ad_unit/{ad_unit_id}?fields=ad_network_settings"
    try:
        r = requests.get(url, headers=_headers(management_key), timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        _log(f"get_ad_unit HATA: {e}")
    return None


def post_ad_unit(management_key: str, ad_unit: dict) -> Tuple[bool, str]:
    """Ad unit'i güncelle. Full config body gönderilir.

    Returns: (success, error_message)
    """
    body = {
        "id":                    ad_unit["id"],
        "name":                  ad_unit["name"],
        "platform":              ad_unit["platform"],
        "ad_format":             ad_unit["ad_format"],
        "package_name":          ad_unit["package_name"],
        "has_active_experiment": ad_unit.get("has_active_experiment", False),
        "disabled":              ad_unit.get("disabled", False),
        "ad_network_settings":   ad_unit["ad_network_settings"],
    }
    url = f"{BASE_URL}/ad_unit/{ad_unit['id']}"
    try:
        r = requests.post(url, headers=_headers(management_key), json=body, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            return False, f"POST {r.status_code}: {r.text[:200]}"
        return True, ""
    except Exception as e:
        return False, str(e)
