import re
import requests
import time
from datetime import datetime
from database import log_operation, update_last_run

BASE_URL = "https://o.applovin.com/mediation/v1"
MAX_RATE_LIMIT_RETRIES = 5

def get_headers(management_key):
    return {
        "Api-Key": management_key,
        "Content-Type": "application/json"
    }

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_all_ad_units(management_key):
    all_units = []
    limit = 100
    offset = 0
    headers = get_headers(management_key)
    rate_limit_retries = 0
    while True:
        url = f"{BASE_URL}/ad_units?fields=ad_network_settings&limit={limit}&offset={offset}"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 429:
                rate_limit_retries += 1
                if rate_limit_retries > MAX_RATE_LIMIT_RETRIES:
                    log(f"HATA: Rate limit {MAX_RATE_LIMIT_RETRIES} kez asildi, durduruluyor")
                    break
                log(f"Rate limit — 60 saniye bekleniyor... (deneme {rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES})")
                time.sleep(60)
                continue
            rate_limit_retries = 0
            if r.status_code != 200:
                log(f"HATA: {r.status_code} — {r.text[:200]}")
                break
            data = r.json()
            if not data:
                break
            all_units.extend(data)
            log(f"  {len(all_units)} ad unit cekildi...")
            if len(data) < limit:
                break
            offset += limit
            time.sleep(0.2)
        except requests.exceptions.Timeout:
            log("HATA: Request timeout (30s)")
            break
        except Exception as e:
            log(f"HATA: {e}")
            break
    return all_units

def find_matches(ad_unit, publisher_tag, find_string):
    """Ad unit içinde publisher_tag + find_string eşleşen entry'leri bul.
    Returns: list of (old_id, new_id) tuples
    """
    matches = []
    for network_obj in ad_unit.get("ad_network_settings", []):
        for network_name, config in network_obj.items():
            if "GOOGLE" not in network_name:
                continue
            for unit in config.get("ad_network_ad_units", []):
                unit_id = unit.get("ad_network_ad_unit_id", "")
                if publisher_tag in unit_id and re.search(re.escape(find_string), unit_id):
                    matches.append(unit_id)
    return matches

def apply_update(ad_unit, management_key, publisher_tag, find_string, replace_string):
    """Bir ad_unit'teki TÜM eşleşen entry'leri tek seferde güncelle ve POST at.
    Returns: (ok, err, expected_new_ids)
    """
    headers = get_headers(management_key)
    expected_new_ids = []

    # In-place değiştir
    for network_obj in ad_unit.get("ad_network_settings", []):
        for network_name, config in network_obj.items():
            if "GOOGLE" not in network_name:
                continue
            for unit in config.get("ad_network_ad_units", []):
                unit_id = unit.get("ad_network_ad_unit_id", "")
                if publisher_tag in unit_id and re.search(re.escape(find_string), unit_id):
                    new_id = re.sub(re.escape(find_string), replace_string, unit_id, count=1)
                    unit["ad_network_ad_unit_id"] = new_id
                    expected_new_ids.append(new_id)

    body = {
        "id":                    ad_unit["id"],
        "name":                  ad_unit["name"],
        "platform":              ad_unit["platform"],
        "ad_format":             ad_unit["ad_format"],
        "package_name":          ad_unit["package_name"],
        "has_active_experiment": ad_unit.get("has_active_experiment", False),
        "disabled":              ad_unit.get("disabled", False),
        "ad_network_settings":   ad_unit["ad_network_settings"]
    }

    url = f"{BASE_URL}/ad_unit/{ad_unit['id']}"
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            return False, f"POST hatasi: {r.status_code} — {r.text[:200]}", expected_new_ids
    except Exception as e:
        return False, str(e), expected_new_ids

    # Verify — her expected_new_id'nin gerçekten yazılıp yazılmadığını kontrol et
    time.sleep(1)
    try:
        r2 = requests.get(f"{url}?fields=ad_network_settings", headers=headers, timeout=30)
        if r2.status_code == 200:
            data = r2.json()
            verified_ids = set()
            for network_obj in data.get("ad_network_settings", []):
                for network_name, config in network_obj.items():
                    if "GOOGLE" not in network_name:
                        continue
                    for unit in config.get("ad_network_ad_units", []):
                        uid = unit.get("ad_network_ad_unit_id", "")
                        if uid in expected_new_ids:
                            verified_ids.add(uid)
            if len(verified_ids) == len(expected_new_ids):
                return True, "", expected_new_ids
            missing = set(expected_new_ids) - verified_ids
            return False, f"Dogrulama basarisiz — eksik: {missing}", expected_new_ids
    except Exception as e:
        return False, f"Dogrulama hatasi: {e}", expected_new_ids
    return False, "Dogrulama yapilamadi", expected_new_ids

def run_refresh(publisher, dry_run=False):
    name         = publisher["name"]
    mgmt_key     = publisher["management_key"]
    tag          = publisher["publisher_tag"]
    find_str     = publisher["find_string"]
    replace_str  = publisher["replace_string"]
    publisher_id = publisher["id"]

    mode = "DRY-RUN" if dry_run else "CANLI"
    log(f"--- {name} [{mode}] basladi ---")
    log(f"  Find: {find_str} -> Replace: {replace_str}")

    ad_units = get_all_ad_units(mgmt_key)
    log(f"  {len(ad_units)} ad unit tarandi")

    success = 0
    failed  = 0
    skipped = 0
    matched = 0

    for ad_unit in ad_units:
        matches = find_matches(ad_unit, tag, find_str)
        if not matches:
            skipped += 1
            continue

        matched += len(matches)

        # Log her match'i
        for old_id in matches:
            new_id = re.sub(re.escape(find_str), replace_str, old_id, count=1)
            log(f"  BULUNDU: {ad_unit['name']} ({ad_unit['id']})")
            log(f"    {old_id}")
            log(f"    -> {new_id}")

        if dry_run:
            for old_id in matches:
                new_id = re.sub(re.escape(find_str), replace_str, old_id, count=1)
                log(f"    [DRY-RUN] Yazilmadi")
                log_operation(publisher_id, name, ad_unit["id"], ad_unit["name"], old_id, new_id, "DRY_RUN")
            continue

        # Canlı run — ad_unit başına TEK POST
        ok, err, expected_new_ids = apply_update(ad_unit, mgmt_key, tag, find_str, replace_str)

        for old_id in matches:
            new_id = re.sub(re.escape(find_str), replace_str, old_id, count=1)
            if ok:
                log(f"    BASARILI + DOGRULANDI")
                log_operation(publisher_id, name, ad_unit["id"], ad_unit["name"], old_id, new_id, "SUCCESS")
                success += 1
            else:
                log(f"    HATA: {err}")
                log_operation(publisher_id, name, ad_unit["id"], ad_unit["name"], old_id, new_id, "FAILED", err)
                failed += 1

        time.sleep(0.3)

    update_last_run(publisher_id)
    log(f"--- {name} bitti | {success} basarili | {failed} hatali | {skipped} atlanan ---")
    return success, failed, skipped, matched

if __name__ == "__main__":
    from database import init_db, get_active_publishers
    init_db()
    publishers = get_active_publishers()
    if not publishers:
        log("Kayitli aktif publisher yok.")
    else:
        for publisher in publishers:
            run_refresh(publisher, dry_run=False)
