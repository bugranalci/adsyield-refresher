"""Google Ad Manager API client.

Makroo'nun service account'u ile GAM'e bağlanır, belirli bir path altındaki
ad unit'leri çeker ve slot bilgilerini parse eder.

GAM REST API kullanıyoruz (google-api-python-client). Service account JWT
ile auth oluyoruz.
"""
import os
import re
import json
from decimal import Decimal
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Sabitler ---

MAKROO_GAM_NETWORK_CODE = "324749355"
GAM_API_SCOPE = "https://www.googleapis.com/auth/dfp"
GAM_API_VERSION = "v202411"

# Slot parse: V8_bnr_aos_5.50 → version=8, format=bnr, platform=aos, cpm=5.50
SLOT_REGEX = re.compile(r"^V(\d+)_([a-z0-9]+)_(aos|ios)_(\d+\.\d+)$", re.IGNORECASE)

# Path template
GAM_PATH_TEMPLATE = "/{network_code},{publisher_id}/2021/{app_name}/"


# --- Service Account Auth ---

_credentials_cache = None

def _load_credentials():
    """Service account JSON'u env'den oku ve credentials oluştur."""
    global _credentials_cache
    if _credentials_cache is not None:
        return _credentials_cache

    json_str = os.getenv("GAM_SERVICE_ACCOUNT_JSON", "")
    if not json_str:
        raise RuntimeError(
            "GAM_SERVICE_ACCOUNT_JSON environment variable'i yok. "
            "Makroo service account JSON'u bu env'e yuklenmeli."
        )

    try:
        info = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GAM_SERVICE_ACCOUNT_JSON gecersiz JSON: {e}")

    creds = service_account.Credentials.from_service_account_info(
        info, scopes=[GAM_API_SCOPE]
    )
    _credentials_cache = creds
    return creds


def _get_gam_service():
    """GAM API service client'ı oluştur."""
    creds = _load_credentials()
    # GAM için discovery document manuel — build_from_document da kullanılabilir
    # Ancak google-ads/ad-manager için genelde SOAP API kullanılır.
    # REST API için admanager.googleapis.com'u kullanacağız.
    return build("admanager", GAM_API_VERSION, credentials=creds, cache_discovery=False)


# --- Path & Slot Helpers ---

def build_app_path(gam_publisher_id: str, app_name: str) -> str:
    """App'in GAM path'ini oluştur."""
    return GAM_PATH_TEMPLATE.format(
        network_code=MAKROO_GAM_NETWORK_CODE,
        publisher_id=gam_publisher_id,
        app_name=app_name,
    )


def build_ad_unit_code(gam_publisher_id: str, app_name: str, version: int,
                       format_: str, platform: str, cpm) -> str:
    """Yeni versiyon ad_network_ad_unit_id oluştur.

    Örnek: /324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50
    """
    cpm_str = f"{float(cpm):.2f}"
    return (
        f"/{MAKROO_GAM_NETWORK_CODE},{gam_publisher_id}/2021/"
        f"{app_name}/V{version}_{format_}_{platform}_{cpm_str}"
    )


def parse_slot_from_name(name: str) -> Optional[dict]:
    """Ad unit ID/name'in son parçasından slot bilgilerini çıkar.

    Input: "/324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50"
    Output: {"version": 8, "format": "bnr", "platform": "aos", "cpm": Decimal("5.50")}

    Parse edilemezse None döner.
    """
    if not name:
        return None
    # Son "/" sonrasını al
    last_segment = name.rsplit("/", 1)[-1]
    m = SLOT_REGEX.match(last_segment)
    if not m:
        return None
    return {
        "version": int(m.group(1)),
        "format": m.group(2).lower(),
        "platform": m.group(3).lower(),
        "cpm": Decimal(m.group(4)),
    }


# --- GAM API ---

def list_ad_units_for_app(gam_publisher_id: str, app_name: str, platform: str) -> list:
    """Bir app'in path'i altındaki tüm GAM ad unit'lerini çek.

    Args:
        gam_publisher_id: "22860626436"
        app_name: "Mackolik"
        platform: "aos" veya "ios"

    Returns:
        [{"name": "V8_bnr_aos_5.50", "full_code": "/324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50", ...}]
        Sadece platform'a uyan slot'lar döner.
    """
    service = _get_gam_service()
    base_path = build_app_path(gam_publisher_id, app_name)

    # GAM API'de `AdUnit` servisi kullanılır. `getAdUnitsByStatement` PQL ile sorgulanır.
    # Ancak REST API'de Ad Manager için InventoryService doğrudan REST olarak sunulmuyor.
    # Bu sebeple googleads-python-lib (SOAP) kullanmak daha güvenilir olabilir.
    #
    # ŞİMDİLİK: Basit bir placeholder yapı — yazılımcı gerçek entegrasyonu yapacak.
    # Aşağıdaki kod AD UNIT listesi çekmek için başlangıç noktası,
    # gerçek hayatta googleads-python-lib ile SOAP API'ye geçilmesi gerekebilir.

    try:
        # admanager REST API — ad units list
        # NOT: Gerçek endpoint ismi GAM versiyonuna göre değişebilir
        network_id = MAKROO_GAM_NETWORK_CODE
        parent = f"networks/{network_id}"

        # AdUnit REST endpoint'i henüz stabil değil — bu yer tutucu
        # Yazılımcı kendi tercihine göre googleads SOAP lib kullanabilir
        request = service.networks().adUnits().list(
            parent=parent,
            filter=f'adUnitCode:"{base_path}"',
            pageSize=500,
        )
        response = request.execute()
        units = response.get("adUnits", [])
    except HttpError as e:
        raise RuntimeError(f"GAM API hatasi: {e}")
    except AttributeError:
        # REST API ad units henüz mevcut değilse, fallback:
        # googleads-python-lib (SOAP) veya manuel HTTP istekleri kullanılmalı
        raise RuntimeError(
            "GAM admanager REST API adUnits endpoint'i bu SDK versiyonunda yok. "
            "Yazilimci googleads-python-lib (SOAP) entegrasyonuna gecmeli."
        )

    # Filter by platform (slot parse'dan platform cikarilir)
    result = []
    for unit in units:
        full_code = unit.get("adUnitCode", "")
        parsed = parse_slot_from_name(full_code)
        if parsed and parsed["platform"] == platform.lower():
            result.append({
                "id": unit.get("adUnitId", ""),
                "name": unit.get("displayName", full_code),
                "full_code": full_code,
                **parsed,
            })
    return result


def get_max_versions_by_slot(gam_publisher_id: str, app_name: str, platform: str) -> dict:
    """Her slot (format+cpm) için GAM'deki max versiyonu döndür.

    Returns:
        {
            ("bnr", "5.50"): 8,
            ("int", "55.00"): 8,
            ("mrec", "7.50"): 8,
            ("mrec2", "6.50"): 8,
        }
    """
    units = list_ad_units_for_app(gam_publisher_id, app_name, platform)

    by_slot = {}
    for unit in units:
        key = (unit["format"], str(unit["cpm"]))
        current = by_slot.get(key, 0)
        if unit["version"] > current:
            by_slot[key] = unit["version"]
    return by_slot


# --- Test / CLI ---

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python gam_client.py <publisher_id> <app_name> [platform]")
        sys.exit(1)
    pid = sys.argv[1]
    app = sys.argv[2]
    plat = sys.argv[3] if len(sys.argv) > 3 else "aos"

    print(f"Path: {build_app_path(pid, app)}")
    try:
        versions = get_max_versions_by_slot(pid, app, plat)
        print(f"Slot max versions: {versions}")
    except Exception as e:
        print(f"HATA: {e}")
