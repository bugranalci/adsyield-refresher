"""Google Ad Manager API client — SOAP tabanlı (googleads-python-lib).

Makroo'nun service account'u ile GAM InventoryService'e bağlanır,
ad unit'leri çeker ve slot bilgilerini parse eder.

GAM REST API henüz AdUnit listeleme için tam olgun değil, bu yüzden
Google'ın resmi googleads-python-lib (SOAP) kütüphanesini kullanıyoruz.
"""
import os
import re
import json
import tempfile
import atexit
import threading
from decimal import Decimal
from typing import Optional

# --- Sabitler ---

MAKROO_GAM_NETWORK_CODE = "324749355"
GAM_API_VERSION = "v202602"  # Quarterly version, Google her 3 ayda günceller

# Slot parse: V8_bnr_aos_5.50 → version=8, format=bnr, platform=aos, cpm=5.50
SLOT_REGEX = re.compile(r"^V(\d+)_([a-z0-9]+)_(aos|ios)_(\d+\.\d+)$", re.IGNORECASE)

# Path template
GAM_PATH_TEMPLATE = "/{network_code},{publisher_id}/2021/{app_name}/"


# --- Service Account Auth + Client Cache ---

_client_cache = None
_key_file_path = None
_lock = threading.Lock()


def _write_service_account_to_tempfile() -> str:
    """GAM_SERVICE_ACCOUNT_JSON env'indeki JSON'u geçici bir dosyaya yaz.

    googleads-python-lib service account için dosya yolu bekliyor,
    in-memory JSON kabul etmiyor. Bu yüzden tempfile kullanıyoruz.
    """
    global _key_file_path
    if _key_file_path and os.path.exists(_key_file_path):
        return _key_file_path

    json_str = os.getenv("GAM_SERVICE_ACCOUNT_JSON", "")
    if not json_str:
        raise RuntimeError(
            "GAM_SERVICE_ACCOUNT_JSON environment variable yok. "
            "Service account JSON'unu Railway Variables'a ekle."
        )

    try:
        # JSON'u parse et ve tekrar dump et (format doğrulaması)
        info = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GAM_SERVICE_ACCOUNT_JSON gecersiz JSON: {e}")

    # Geçici dosya oluştur (process bittiğinde otomatik silinecek)
    fd, path = tempfile.mkstemp(suffix=".json", prefix="gam_sa_")
    with os.fdopen(fd, "w") as f:
        json.dump(info, f)

    _key_file_path = path
    atexit.register(_cleanup_keyfile)
    return path


def _cleanup_keyfile():
    """Process kapandığında temp key file'ı sil."""
    global _key_file_path
    if _key_file_path and os.path.exists(_key_file_path):
        try:
            os.unlink(_key_file_path)
        except Exception:
            pass


def _get_client():
    """googleads AdManagerClient instance'ı oluştur (cached)."""
    global _client_cache
    with _lock:
        if _client_cache is not None:
            return _client_cache

        # Lazy import — googleads kütüphanesi ağır, startup'ı yavaşlatmamak için
        from googleads import ad_manager, oauth2

        key_path = _write_service_account_to_tempfile()

        oauth2_client = oauth2.GoogleServiceAccountClient(
            key_path,
            oauth2.GetAPIScope("ad_manager"),
        )

        client = ad_manager.AdManagerClient(
            oauth2_client,
            "adsyield-refresher",
            network_code=MAKROO_GAM_NETWORK_CODE,
        )
        _client_cache = client
        return client


# --- Path & Slot Helpers ---

def build_app_path(gam_publisher_id: str, app_name: str) -> str:
    """App'in GAM path prefix'ini oluştur."""
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
    """
    if not name:
        return None
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


def _build_full_path(unit) -> str:
    """GAM AdUnit object'inden full path'i oluştur.

    AdUnit'te parentPath (list of {id, name, adUnitCode}) ve kendi adUnitCode var.
    Bunları birleştirip "/324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50"
    formatına çeviriyoruz.
    """
    parts = []
    parent_path = unit.get("parentPath", []) if isinstance(unit, dict) else getattr(unit, "parentPath", [])

    if parent_path:
        for parent in parent_path:
            code = parent.get("adUnitCode") if isinstance(parent, dict) else getattr(parent, "adUnitCode", None)
            if code:
                parts.append(code)

    own_code = unit.get("adUnitCode") if isinstance(unit, dict) else getattr(unit, "adUnitCode", None)
    if own_code:
        parts.append(own_code)

    return "/" + "/".join(parts) if parts else ""


# --- GAM API ---

def list_ad_units_for_app(gam_publisher_id: str, app_name: str, platform: str) -> list:
    """Bir app'in path'i altındaki slot pattern'ına uyan GAM ad unit'lerini çek.

    Strateji: Network'teki tüm ACTIVE ad unit'leri pagination ile çek,
    Python tarafında path prefix + slot regex ile filtrele.

    Args:
        gam_publisher_id: "22860626436"
        app_name: "Mackolik"
        platform: "aos" veya "ios"

    Returns:
        [{"id", "name", "full_code", "version", "format", "platform", "cpm"}]
    """
    from googleads import ad_manager

    client = _get_client()
    service = client.GetService("InventoryService", version=GAM_API_VERSION)

    expected_prefix = build_app_path(gam_publisher_id, app_name)

    # Pagination
    all_units = []
    offset = 0
    page_size = 500

    while True:
        statement = (
            ad_manager.StatementBuilder(version=GAM_API_VERSION)
            .Where("status = :status")
            .WithBindVariable("status", "ACTIVE")
            .Limit(page_size)
            .Offset(offset)
        )

        try:
            response = service.getAdUnitsByStatement(statement.ToStatement())
        except Exception as e:
            raise RuntimeError(f"GAM getAdUnitsByStatement hatasi: {e}")

        if not response or "results" not in response or not response["results"]:
            break

        batch = response["results"]
        all_units.extend(batch)

        if len(batch) < page_size:
            break
        offset += page_size

    # Python tarafında filtrele
    result = []
    for unit in all_units:
        full_path = _build_full_path(unit)
        if not full_path:
            continue

        # Path prefix kontrolü
        if expected_prefix not in full_path:
            continue

        # Slot pattern kontrolü
        parsed = parse_slot_from_name(full_path)
        if not parsed:
            continue

        # Platform kontrolü
        if parsed["platform"] != platform.lower():
            continue

        unit_id = unit.get("id") if isinstance(unit, dict) else getattr(unit, "id", None)
        name = unit.get("name") if isinstance(unit, dict) else getattr(unit, "name", "")

        result.append({
            "id": str(unit_id) if unit_id else "",
            "name": name or full_path,
            "full_code": full_path,
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
        key = (unit["format"], f"{float(unit['cpm']):.2f}")
        current = by_slot.get(key, 0)
        if unit["version"] > current:
            by_slot[key] = unit["version"]
    return by_slot


# --- Test / CLI ---

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python gam_client.py <publisher_id> <app_name> [platform]")
        print("Example: python gam_client.py 22860626436 Mackolik aos")
        sys.exit(1)
    pid = sys.argv[1]
    app = sys.argv[2]
    plat = sys.argv[3] if len(sys.argv) > 3 else "aos"

    print(f"Path prefix: {build_app_path(pid, app)}")
    print(f"Platform filter: {plat}")
    print()

    try:
        units = list_ad_units_for_app(pid, app, plat)
        print(f"Bulunan ad unit sayisi: {len(units)}")
        for u in units[:10]:
            print(f"  V{u['version']} {u['format']}_{u['platform']}_{u['cpm']}  — {u['full_code']}")
        if len(units) > 10:
            print(f"  ... ve {len(units) - 10} tane daha")

        print()
        versions = get_max_versions_by_slot(pid, app, plat)
        print("Slot max versions:")
        for key, max_v in versions.items():
            print(f"  {key[0]}_{plat}_{key[1]}: V{max_v}")
    except Exception as e:
        print(f"HATA: {e}")
        import traceback
        traceback.print_exc()
