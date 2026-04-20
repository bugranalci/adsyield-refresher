"""Sync motoru — bir app için GAM'deki max versiyonları MAX waterfall ile karşılaştır
ve güncellemeleri uygula.

Yeni mantık (slot-based):
  1. GAM'den app'in her slot'u için max version al (gam_client)
  2. MAX'ten publisher'ın tüm ad unit'lerini çek (max_client)
  3. Her ad unit'in ad_network_settings'inde GOOGLE network entry'lerini bul
  4. Her entry'nin ad_network_ad_unit_id'sini parse et (slot bilgisi)
  5. Slot'un GAM max version > MAX mevcut version ise güncelleme adayı
  6. Dry run: sadece raporla. Canlı run: snapshot al + POST + verify
"""
import copy
import time
from datetime import datetime
from typing import Tuple, List

from gam_client import (
    parse_slot_from_name, build_ad_unit_code, get_max_versions_by_slot,
)
from max_client import list_all_ad_units, get_ad_unit, post_ad_unit
from database import (
    log_operation, update_app_last_run, create_snapshot, upsert_slot_cache,
    clear_slot_cache,
)


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [ENGINE] {msg}")


def _extract_google_entries(ad_unit: dict, platform: str) -> List[tuple]:
    """Bir MAX ad unit'inin GOOGLE network entry'lerini çıkar.

    Returns:
        [(network_obj, network_name, unit_dict, slot_info), ...]
        slot_info = {"version", "format", "platform", "cpm"} or None
    """
    results = []
    for network_obj in ad_unit.get("ad_network_settings", []):
        for network_name, config in network_obj.items():
            if "GOOGLE" not in network_name:
                continue
            for unit in config.get("ad_network_ad_units", []):
                unit_id = unit.get("ad_network_ad_unit_id", "")
                slot_info = parse_slot_from_name(unit_id)
                if slot_info and slot_info["platform"] == platform.lower():
                    results.append((network_obj, network_name, unit, slot_info))
    return results


def compute_updates_for_app(app: dict, gam_max_versions: dict, ad_units: list) -> list:
    """Her MAX ad unit'te güncellenmesi gereken entry'leri hesapla.

    Args:
        app: {"id", "gam_app_name", "platform", "publisher": {...}}
        gam_max_versions: {(format, cpm_str): max_version}
        ad_units: MAX'ten çekilen ad unit listesi

    Returns:
        [
          {
            "max_ad_unit": <full ad_unit dict>,
            "entries": [
              {
                "old_id": "/324.../V7_bnr_aos_5.50",
                "new_id": "/324.../V8_bnr_aos_5.50",
                "slot": {...},
                "new_version": 8,
              },
              ...
            ]
          },
          ...
        ]
    """
    platform = app["platform"]
    gam_app_name = app["gam_app_name"]
    gam_publisher_id = app["gam_publisher_id"]

    updates = []
    for ad_unit in ad_units:
        entries_to_update = []
        google_entries = _extract_google_entries(ad_unit, platform)

        for network_obj, network_name, unit, slot in google_entries:
            # Sadece bu app'e ait ad unit'leri güncelle (gam_app_name path'inde olmalı)
            unit_id = unit.get("ad_network_ad_unit_id", "")
            if f"/{gam_app_name}/" not in unit_id:
                continue

            key = (slot["format"], f"{float(slot['cpm']):.2f}")
            gam_max = gam_max_versions.get(key)
            if gam_max is None:
                # GAM'de bu slot yok — elle manipüle edilmiş olabilir, atla
                continue
            if slot["version"] >= gam_max:
                # MAX zaten güncel
                continue

            new_id = build_ad_unit_code(
                gam_publisher_id=gam_publisher_id,
                app_name=gam_app_name,
                version=gam_max,
                format_=slot["format"],
                platform=slot["platform"],
                cpm=slot["cpm"],
            )
            entries_to_update.append({
                "network_obj": network_obj,
                "network_name": network_name,
                "unit_ref": unit,  # dict reference — in-place değiştirilecek
                "old_id": unit_id,
                "new_id": new_id,
                "slot": slot,
                "new_version": gam_max,
            })

        if entries_to_update:
            updates.append({
                "max_ad_unit": ad_unit,
                "entries": entries_to_update,
            })
    return updates


def sync_app(app: dict, run_job_id: str, dry_run: bool = True) -> dict:
    """Bir app için tam sync akışı.

    Args:
        app: {"id", "label", "gam_app_name", "platform", "publisher_id",
              "gam_publisher_id", "management_key", "publisher_name"}
        run_job_id: Snapshot ve log ilişkisi için
        dry_run: True ise MAX'e yazmaz

    Returns:
        {
            "status": "done" | "no_match",
            "matched": int,
            "success": int,
            "failed": int,
            "skipped": int,
            "gam_versions": dict,
            "dry_run": bool,
        }
    """
    mode = "DRY-RUN" if dry_run else "CANLI"
    _log(f"--- {app['label']} [{mode}] basladi ---")

    mgmt_key = app["management_key"]
    platform = app["platform"]

    # 1. GAM'den max versiyonları çek
    _log(f"  GAM'den slot durumu cekiliyor: {app['gam_app_name']}/{platform}")
    try:
        gam_versions = get_max_versions_by_slot(
            app["gam_publisher_id"], app["gam_app_name"], platform
        )
    except Exception as e:
        _log(f"  GAM HATA: {e}")
        return {"status": "gam_error", "matched": 0, "success": 0, "failed": 0,
                "skipped": 0, "gam_versions": {}, "dry_run": dry_run,
                "error": str(e)}

    _log(f"  GAM max versions: {gam_versions}")

    # Slot cache'i güncelle
    clear_slot_cache(app["id"])
    for (fmt, cpm_str), max_v in gam_versions.items():
        upsert_slot_cache(app["id"], fmt, platform, cpm_str, max_v)

    # 2. MAX'ten ad unit'leri çek
    ad_units = list_all_ad_units(mgmt_key)
    _log(f"  {len(ad_units)} MAX ad unit tarandi")

    # 3. Güncellemeleri hesapla
    updates = compute_updates_for_app(app, gam_versions, ad_units)
    matched = sum(len(u["entries"]) for u in updates)
    skipped = len(ad_units) - len(updates)

    _log(f"  {matched} entry guncellenecek ({len(updates)} ad unit'te)")

    if matched == 0:
        update_app_last_run(app["id"])
        _log(f"--- {app['label']} bitti | eslesme yok ---")
        return {"status": "no_match", "matched": 0, "success": 0, "failed": 0,
                "skipped": skipped, "gam_versions": gam_versions, "dry_run": dry_run}

    success = 0
    failed = 0

    for update in updates:
        ad_unit = update["max_ad_unit"]
        entries = update["entries"]

        # Log her entry'i
        for e in entries:
            _log(f"  BULUNDU: {ad_unit.get('name', '?')} — V{e['slot']['version']} → V{e['new_version']}")

        if dry_run:
            for e in entries:
                log_operation(
                    publisher_id=app["publisher_id"],
                    publisher_name=app.get("publisher_name", ""),
                    app_id=app["id"], app_label=app["label"],
                    run_job_id=run_job_id,
                    ad_unit_id=ad_unit["id"], ad_unit_name=ad_unit.get("name", ""),
                    old_value=e["old_id"], new_value=e["new_id"],
                    status="DRY_RUN",
                )
            continue

        # Canlı run: önce snapshot al (orijinal full config)
        snapshot_config = copy.deepcopy(ad_unit)
        for e in entries:
            create_snapshot(
                app_id=app["id"],
                run_job_id=run_job_id,
                max_ad_unit_id=ad_unit["id"],
                max_ad_unit_name=ad_unit.get("name", ""),
                old_id=e["old_id"],
                new_id=e["new_id"],
                full_config=snapshot_config,
            )

        # Ad unit'i in-place güncelle (tüm entry'ler için)
        for e in entries:
            e["unit_ref"]["ad_network_ad_unit_id"] = e["new_id"]

        # POST
        ok, err = post_ad_unit(mgmt_key, ad_unit)

        # Verify
        if ok:
            time.sleep(1)
            verified = _verify_updates(mgmt_key, ad_unit["id"], entries, platform)
            if not verified:
                ok = False
                err = "Dogrulama basarisiz"

        for e in entries:
            if ok:
                log_operation(
                    publisher_id=app["publisher_id"],
                    publisher_name=app.get("publisher_name", ""),
                    app_id=app["id"], app_label=app["label"],
                    run_job_id=run_job_id,
                    ad_unit_id=ad_unit["id"], ad_unit_name=ad_unit.get("name", ""),
                    old_value=e["old_id"], new_value=e["new_id"],
                    status="SUCCESS",
                )
                success += 1
            else:
                log_operation(
                    publisher_id=app["publisher_id"],
                    publisher_name=app.get("publisher_name", ""),
                    app_id=app["id"], app_label=app["label"],
                    run_job_id=run_job_id,
                    ad_unit_id=ad_unit["id"], ad_unit_name=ad_unit.get("name", ""),
                    old_value=e["old_id"], new_value=e["new_id"],
                    status="FAILED", error_message=err,
                )
                failed += 1

        time.sleep(0.3)

    update_app_last_run(app["id"])
    _log(f"--- {app['label']} bitti | {success} basarili | {failed} hatali | {skipped} atlanan ---")

    return {
        "status": "done",
        "matched": matched,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "gam_versions": gam_versions,
        "dry_run": dry_run,
    }


def _verify_updates(management_key: str, ad_unit_id: str, entries: list, platform: str) -> bool:
    """POST sonrası her expected new_id'nin gerçekten yazıldığını doğrula."""
    data = get_ad_unit(management_key, ad_unit_id)
    if not data:
        return False

    expected = {e["new_id"] for e in entries}
    found = set()
    for network_obj in data.get("ad_network_settings", []):
        for network_name, config in network_obj.items():
            if "GOOGLE" not in network_name:
                continue
            for unit in config.get("ad_network_ad_units", []):
                uid = unit.get("ad_network_ad_unit_id", "")
                if uid in expected:
                    found.add(uid)
    return expected == found


# --- Rollback ---

def rollback_snapshot(snapshot: dict, management_key: str) -> Tuple[bool, str]:
    """Bir snapshot'ı kullanarak MAX waterfall'daki ad unit'i eski haline döndür.

    Args:
        snapshot: DB'den gelen snapshot dict (full_config içerir)
        management_key: MAX API key

    Returns:
        (success, error_message)
    """
    if not snapshot.get("full_config"):
        return False, "Snapshot'ta full_config yok"

    # full_config JSON olarak saklandı — zaten dict veya str olabilir
    full_config = snapshot["full_config"]
    if isinstance(full_config, str):
        import json
        full_config = json.loads(full_config)

    # Snapshot'taki tam config ile POST at
    ok, err = post_ad_unit(management_key, full_config)
    return ok, err
