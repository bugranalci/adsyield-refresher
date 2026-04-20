# ADSYIELD Refresh Tool

AppLovin MAX waterfall'undaki GAM (Google Ad Manager) ad unit'lerinin **Makroo tarafındaki versiyonlarını takip ederek** otomatik güncellenmesini sağlayan dahili araç.

---

## Bu Proje Ne Yapıyor?

Makroo (MCM partner), bağlı olduğu yayıncılara GAM üzerinden çeşitli formatlarda (banner, interstitial, mrec, rewarded) ve CPM price'larla ad unit'ler veriyor. Bu ad unit'ler yayıncının AppLovin MAX waterfall'unda yer alıyor.

Makroo zaman zaman **yeni versiyon ad unit'ler** oluşturuyor (ör: `V7_bnr_aos_5.50` → `V8_bnr_aos_5.50`). Bu yeni versiyonların yayıncının MAX waterfall'una işlenmesi gerekiyor — bu işleme **refresh** diyoruz.

Bu tool:
1. Makroo'nun GAM hesabından yeni versiyonları tespit eder
2. Yayıncının MAX waterfall'undaki mevcut versiyonlarla karşılaştırır
3. Account manager'a (AM) değişiklik raporunu gösterir (dry run)
4. AM onaylarsa, MAX waterfall'unu günceller ve doğrular
5. Hata durumunda her ad unit ayrı ayrı eski haline döndürülebilir (rollback)

### Temel Kavramlar

| Terim | Açıklama |
|---|---|
| **Publisher** | Yayıncı (ör: Mackolik) — bir AppLovin MAX hesabı ve bir GAM publisher ID'si var |
| **App** | Yayıncının oyunu/uygulaması — her platform (AOS/iOS) ayrı app sayılır |
| **Slot** | Belirli bir format + platform + CPM kombinasyonu (ör: `bnr_aos_5.50`) |
| **Version** | Slot'un versiyonu (V1, V2, V3...) — Makroo zamanla artırır |
| **Management Key** | Yayıncının AppLovin MAX API anahtarı |
| **GAM Publisher ID** | Yayıncının Makroo'nun GAM hesabındaki benzersiz numarası |
| **Snapshot** | Run öncesi waterfall'ın anlık kaydı — rollback için kullanılır |
| **Dry Run** | Waterfall'a dokunmadan sadece raporlayan test çalıştırma |
| **Canlı Run** | Gerçek değişiklikleri yapan ve doğrulayan çalıştırma |

---

## GAM Ad Unit Pattern

Makroo'nun GAM'de oluşturduğu ad unit'lerin path yapısı:

```
/324749355,{PUBLISHER_GAM_ID}/2021/{APP_NAME}/V{N}_{format}_{platform}_{cpm}

Örnek: /324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50
       └────────┬─────────┘└──┬─┘└───┬───┘└────┬─────────┘
            Sabit kısım    Publisher  App     Slot info
                             GAM ID   adı    ├─ V8: Version
                                              ├─ bnr: Format
                                              ├─ aos: Platform
                                              └─ 5.50: CPM
```

### Sabit ve Değişken Parçalar

| Parça | Sabit/Değişken | Örnek |
|---|---|---|
| `/324749355/` | Sabit | Makroo GAM Network Code |
| `{PUBLISHER_GAM_ID}` | Publisher bazlı | `22860626436` (Mackolik), `22852013765` (GetContact) |
| `/2021/` | Sabit | Makroo'nun klasör yapısı |
| `{APP_NAME}` | App bazlı | `Mackolik`, `GetContact` |
| `V{N}` | Değişken | `V1`, `V2`, `V8` — max olan en güncel |
| `{format}` | Slot bazlı | `bnr`, `int`, `mrec`, `mrec2`, `rew` |
| `{platform}` | Slot bazlı | `aos`, `ios` |
| `{cpm}` | Slot bazlı | `5.50`, `55.00`, `7.50` |

### Format Kısaltmaları

| Kısaltma | Anlamı |
|---|---|
| `bnr` | Banner |
| `int` | Interstitial |
| `mrec` | MREC (varyasyonlar için `mrec2` gibi ek sayı olabilir) |
| `rew` | Rewarded |

**Önemli:** Bir app'te aynı format için **birden fazla slot** olabilir (farklı CPM tier'ları):
- `V8_mrec_aos_7.50` (mrec1, $7.50 CPM)
- `V8_mrec2_aos_6.50` (mrec2, $6.50 CPM)

Bunlar sistem açısından **farklı slot'lar** sayılır ve bağımsız versiyonlanırlar.

**CPM sabitliği:** Aynı slot için CPM değişmez. Yani `V8_bnr_aos_5.50` → `V9_bnr_aos_5.50` olur, `V9_bnr_aos_6.00` OLMAZ. CPM değişirse ayrı bir slot sayılır.

---

## Mimari

```
┌─────────────────────────────────────────────────────────┐
│                      Railway                             │
│                                                          │
│  ┌──────────┐    ┌────────────────────────────────┐    │
│  │ React UI │───▶│       FastAPI Backend          │    │
│  │ (build/) │    │  Port 8000 + APIRouter /api/   │    │
│  └──────────┘    │                                │    │
│                  │  api.py      → HTTP endpoints  │    │
│                  │  engine.py   → Sync motoru     │    │
│                  │  gam_client.py → GAM API       │    │
│                  │  max_client.py → MAX API       │    │
│                  │  db.py       → SQLAlchemy      │    │
│                  │  scheduler.py → Cron job'ları  │    │
│                  │  mailer.py   → Email           │    │
│                  │  auth.py     → JWT             │    │
│                  └────────┬───────────────────────┘    │
│                           │                             │
│        ┌──────────────────┴────────────────┐           │
│        ▼                                   ▼           │
│  ┌──────────────┐                 ┌──────────────┐    │
│  │ PostgreSQL   │                 │ GAM Service  │    │
│  │ (Railway DB) │                 │ Account Key  │    │
│  └──────────────┘                 │ (env var)    │    │
│                                   └──────────────┘    │
└─────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
    AppLovin MAX API                    Google Ad Manager API
    o.applovin.com/mediation/v1          adx api
```

### Teknoloji

- **Backend:** Python 3.12 + FastAPI + Uvicorn + SQLAlchemy
- **Frontend:** React 19 (build → FastAPI serve)
- **Database:** PostgreSQL (Railway managed) — local dev'de SQLite fallback
- **Auth:** JWT token (24 saat geçerlilik)
- **Deploy:** Railway (Docker, tek servis)
- **External APIs:**
  - AppLovin MAX Management API
  - Google Ad Manager API (service account)

### Dosya Yapısı

```
├── api.py                 # FastAPI endpoint'leri
├── engine.py              # Sync motoru (slot karşılaştırma + update)
├── gam_client.py          # Google Ad Manager API client
├── max_client.py          # AppLovin MAX API client (engine'den ayrıldı)
├── db.py                  # SQLAlchemy modelleri ve session
├── scheduler.py           # Cron job'ları (slot sync, snapshot cleanup)
├── mailer.py              # Email gönderimi
├── auth.py                # JWT auth
├── requirements.txt       # Python deps
├── Dockerfile             # Multi-stage build
├── .env.production        # React prod env
├── src/                   # React kaynak
│   ├── api.js             # Frontend API client
│   ├── App.js             # Ana uygulama
│   └── components/
│       ├── Login.js
│       ├── PublisherList.js
│       ├── PublisherForm.js
│       ├── AppList.js           # YENİ — bir publisher'ın app'leri
│       ├── AppForm.js           # YENİ — app ekleme/düzenleme
│       ├── AppDetail.js         # YENİ — slot status + run
│       ├── ApprovalList.js      # Hybrid mod onayları
│       └── LogViewer.js         # + Rollback butonları
└── public/
```

---

## Çalışma Prensipleri

### Manuel Mod (Faz 1 — Aktif)

Account manager tüm işlemleri manuel yapar.

```
AM giriş yapar
    │
    ▼
Publisher ekler (name, management_key, gam_publisher_id, ...)
    │
    ▼
O publisher'a app'ler ekler (label, gam_app_name, platform)
    │
    ▼
Bir app'e tıklar → Slot status görür
    │
    ▼
"Dry Run" basar
    │
    ▼
Sistem:
  1. GAM'den o app'in tüm slot'larının max versiyonlarını çeker
  2. MAX'ten o publisher'ın waterfall'ını çeker
  3. Waterfall'daki her ad unit'in slot bilgisini parse eder
  4. Her slot için: MAX versiyonu < GAM max versiyonu ise güncelleme gerekir
  5. Raporu AM'e gösterir (eski ID → yeni ID listesi)
    │
    ▼
AM inceler
    │
    ▼
"Run" basar
    │
    ▼
Sistem:
  1. Snapshot alır (etkilenen ad unit'lerin mevcut hali)
  2. MAX API'ye POST atar, ad unit'leri günceller
  3. Her güncellemeyi verify eder (GET ile doğrulama)
  4. Her operasyonu job_logs'a yazar (SUCCESS/FAILED)
    │
    ▼
AM Job Logs sayfasından sonucu inceler
    │
    ▼
Sorun varsa: Belirli ad unit'lerin yanındaki "Rollback" butonuna basar
             → Sistem snapshot'tan eski ID'yi alır, MAX'e POST eder, eski haline döndürür
```

### Hibrit Mod (Faz 2)

Scheduler otomatik çalışır, AM sadece email'le gelen onay linkine basar.

```
Her gün 03:00 — Scheduler slot cache sync yapar (tüm hybrid app'ler için GAM taraması)
    │
    ▼
Scheduler hybrid app'leri kontrol eder
    │
    ▼
Bir app'te GAM max version > MAX mevcut version tespit edilirse:
    │
    ▼
Otomatik Dry Run çalıştırır
    │
    ▼
Sonuçları AM'e email gönderir
    │
    ┌────────────────────────────────────────┐
    │  ADSYIELD — Güncelleme Onayı           │
    │                                        │
    │  Publisher: Mackolik                   │
    │  App: Mackolik AOS                     │
    │  Güncelleme: 8 slot'ta yeni versiyon   │
    │                                        │
    │  V7_bnr_aos_5.50   →  V8_bnr_aos_5.50 │
    │  V7_int_aos_55.00  →  V8_int_aos_55.00│
    │  ...                                   │
    │                                        │
    │  [Detayları Gör ve Onayla]             │
    └────────────────────────────────────────┘
    │
    ▼
AM linke tıklar → UI'da Approvals sayfası açılır
    │
    ▼
Detayları inceler
    │
    ▼
"Confirm Run" basar → Canlı run tetiklenir (manuel moddaki gibi snapshot + verify)
    │
    ▼
48 saat içinde onaylanmazsa → Otomatik expire, bir şey yapılmaz
```

---

## Veritabanı Şeması

### publishers
| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| name | TEXT | Yayıncı adı (ör: Mackolik) |
| management_key | TEXT | AppLovin MAX API anahtarı |
| gam_publisher_id | TEXT | Makroo GAM'deki yayıncı ID'si (ör: 22860626436) |
| notify_email | TEXT | Hybrid modda bildirim email'i |
| mode | TEXT | `manual` veya `hybrid` |
| frequency_days | INT | Hybrid modda kontrol sıklığı |
| active | INT | 1 = aktif |
| last_run | TIMESTAMP | — |
| created_at | TIMESTAMP | — |

### apps
| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| publisher_id | INT FK | — |
| label | TEXT | AM'in gördüğü isim (ör: "Mackolik AOS") |
| gam_app_name | TEXT | GAM path'indeki klasör adı (ör: "Mackolik") |
| platform | TEXT | `aos` veya `ios` |
| active | INT | 1 = aktif |
| last_run | TIMESTAMP | — |
| created_at | TIMESTAMP | — |

### slot_cache
GAM'den çekilen slot durumunun cache'i. Günlük 03:00'da scheduler güncelller.

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| app_id | INT FK | — |
| format | TEXT | `bnr`, `int`, `mrec`, `mrec2`, `rew` |
| platform | TEXT | `aos`, `ios` |
| cpm | DECIMAL | CPM değeri |
| max_version | INT | GAM'de bulunan en güncel versiyon |
| synced_at | TIMESTAMP | — |

### snapshots
Her run öncesi alınan snapshot — rollback için.

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| app_id | INT FK | — |
| run_job_id | TEXT | Run'un benzersiz ID'si |
| max_ad_unit_id | TEXT | MAX'teki parent ad unit ID |
| network_ad_unit_id_old | TEXT | Değişiklik öncesi GAM ad unit ID |
| network_ad_unit_id_new | TEXT | Değişiklik sonrası GAM ad unit ID |
| full_config | JSONB | Run öncesi tam ad_network_settings (rollback için) |
| status | TEXT | `active`, `rolled_back` |
| created_at | TIMESTAMP | — |
| rolled_back_at | TIMESTAMP NULL | — |

### job_logs
Her ad unit operasyonunun detayı.

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| publisher_id | INT FK | — |
| app_id | INT FK | — |
| run_job_id | TEXT | — |
| ad_unit_name | TEXT | — |
| old_value | TEXT | — |
| new_value | TEXT | — |
| status | TEXT | `SUCCESS`, `FAILED`, `DRY_RUN`, `ROLLED_BACK` |
| error_message | TEXT | — |
| ran_at | TIMESTAMP | — |

### pending_approvals
Hibrit mod dry run sonuçları, AM onayı bekliyor.

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INT PK | — |
| app_id | INT FK | — |
| job_id | TEXT UNIQUE | — |
| matched | INT | Değişecek ad unit sayısı |
| status | TEXT | `pending`, `approved`, `expired` |
| created_at | TIMESTAMP | — |
| expires_at | TIMESTAMP | created_at + 48 saat |
| approved_at | TIMESTAMP NULL | — |

---

## API Endpoint'leri

Tüm endpoint'ler `/api/` prefix'i altında. `/api/login` hariç hepsi JWT token gerektirir.

Header: `Authorization: Bearer <token>`

### Auth
| Method | Endpoint | Açıklama |
|---|---|---|
| POST | `/api/login` | Email + şifre → JWT token |

### Publishers
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/publishers` | Tüm publisher'lar |
| POST | `/api/publishers` | Yeni publisher |
| PUT | `/api/publishers/{id}` | Güncelle |
| DELETE | `/api/publishers/{id}` | Sil (cascade) |
| GET | `/api/publishers/{id}/apps` | O publisher'ın app'leri |

### Apps
| Method | Endpoint | Açıklama |
|---|---|---|
| POST | `/api/apps` | Yeni app (publisher_id, label, gam_app_name, platform) |
| PUT | `/api/apps/{id}` | Güncelle |
| DELETE | `/api/apps/{id}` | Sil |
| GET | `/api/apps/{id}/slot-status` | Slot cache durumu (cache + MAX karşılaştırması) |
| POST | `/api/apps/{id}/refresh-slots` | Manuel slot cache yenile (AM butonu) |
| POST | `/api/apps/{id}/run?dry_run=true` | Dry run veya canlı run başlat |

### Jobs
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/jobs/{job_id}` | İş durumu (polling) |

### Approvals (Hibrit Mod)
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/approvals` | Bekleyen onaylar |
| GET | `/api/approvals/{job_id}` | Onay detayı |
| POST | `/api/approvals/{job_id}/confirm` | Onayla → canlı run |

### Snapshots / Rollback
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/snapshots?app_id=X` | Bir app'in snapshot'ları |
| POST | `/api/snapshots/{id}/rollback` | Snapshot'tan geri yükle |

### Logs
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/logs?app_id=X` | Job log'ları |

---

## Environment Variables

### Zorunlu

| Değişken | Açıklama |
|---|---|
| `JWT_SECRET` | Token imzalama anahtarı — production'da güçlü random string |
| `DATABASE_URL` | PostgreSQL bağlantı URL'i (Railway otomatik oluşturur) |
| `GAM_SERVICE_ACCOUNT_JSON` | Google Ad Manager service account JSON (tek satır) |

### Opsiyonel

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | İzinli origin'ler |
| `SMTP_HOST` | `smtp.gmail.com` | Email SMTP sunucusu |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | Gmail adresi |
| `SMTP_PASS` | — | Gmail App Password |
| `APP_URL` | `http://localhost:3000` | Email linklerinde kullanılan URL |
| `JWT_EXPIRE_HOURS` | `24` | Token geçerlilik |
| `AUTH_USERS` | — | `email1:bcrypt_hash1,email2:bcrypt_hash2` formatında |

---

## Sabit Değerler (Kod İçi)

Bunlar kod içinde sabit olarak tutulur, env variable değildir:

- `MAKROO_GAM_NETWORK_CODE = 324749355`
- `GAM_PATH_TEMPLATE = "/{network_code},{publisher_id}/2021/{app_name}/"`
- `SLOT_REGEX = r"^V(\d+)_([a-z0-9]+)_(aos|ios)_(\d+\.\d+)$"`
- `SCHEDULER_CRON = "0 3 * * *"` (her gün 03:00)
- `SNAPSHOT_RETENTION_DAYS = 30`
- `APPROVAL_EXPIRE_HOURS = 48`
- `MAX_API_RATE_LIMIT_RETRIES = 5`

---

## Lokal Geliştirme

### Gereksinimler
- Python 3.9+
- Node.js 18+
- PostgreSQL (veya local SQLite fallback ile geçici)

### Kurulum

```bash
git clone https://github.com/bugranalci/adsyield-refresher.git
cd adsyield-refresher

# Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node
npm install

# Env
export DATABASE_URL="postgresql://user:pass@localhost:5432/adsyield"
# veya SQLite fallback için:
export DATABASE_URL="sqlite:///adsyield.db"

export GAM_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export JWT_SECRET="local-dev-secret"

# Backend (port 8000)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Ayrı terminal — Frontend (port 3000)
npm start
```

### Test Kullanıcıları

| Email | Şifre |
|---|---|
| `bnalci@adsyield.com` | `Adsyield-2026-*` |
| `ocakir@adsyield.com` | `Adsyield-2025-*` |

---

## Deploy — Railway

### 1. PostgreSQL Servisi

1. Railway dashboard → Projeye git → **+ New**
2. **Database** → **PostgreSQL** seç
3. Otomatik olarak `DATABASE_URL` env variable'ı oluşur, ana servise bağlanır

### 2. Environment Variables

Railway dashboard → Servis → **Variables** sekmesi:

```
JWT_SECRET=<güçlü-random-string>
GAM_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"makrooproject",...}
CORS_ORIGINS=*
APP_URL=https://adsyield-refresher-production.up.railway.app
SMTP_USER=<gmail>
SMTP_PASS=<gmail-app-password>
```

### 3. Deploy

GitHub push → Railway otomatik deploy eder.

### 4. Custom Domain

1. Hostinger DNS: CNAME kaydı → `refresh.adsyield.com` → `adsyield-refresher-production.up.railway.app`
2. Railway → Settings → Networking → Custom Domain → `refresh.adsyield.com`
3. SSL otomatik oluşur
4. `APP_URL` env variable'ını yeni domain'e güncelle

---

## GAM Entegrasyonu — Makroo Yazılımcısı İçin

### Service Account

Makroo, bize kendi GAM hesabında bir **Service Account** oluşturdu. Service account JSON dosyası `GAM_SERVICE_ACCOUNT_JSON` env variable olarak Railway'e yüklü.

### Erişim Modeli

Makroo MCM yapısı kullanıyor — kendi GAM hesabından yayıncılara ad unit veriyor. Bu service account Makroo'nun hesabına bağlı, dolayısıyla:

- **Tüm yayıncıların ad unit'lerine** Makroo'nun hesabı üzerinden erişim var
- Her yayıncıdan ayrı key almaya gerek yok
- `GAM publisher_id` = yayıncının Makroo'daki child ID'si (path'teki `22860626436` gibi)

### Kullanılan GAM API

- **SDK:** `googleads-python-lib`
- **Service:** `InventoryService.getAdUnitsByStatement()`
- **Filtre:** `parentId` veya `AdUnit.name LIKE`
- **Auth:** Service account JWT

### Gerçek Test

Makroo test ad unit'leri sağladı (GAM ID: 86335799):

```
/86335799/game1/v1_masthead, v2_masthead, v3_masthead
/86335799/game1/v1_rewarded, v2_rewarded, v3_rewarded
/86335799/game2/...
/86335799/game3/...
```

**Not:** Test pattern (`v1_masthead`) production pattern'dan (`V1_bnr_aos_5.50`) farklı. Sistem production pattern'a göre yazılmıştır. Test için Makroo yazılımcısı production pattern'da test data üretebilir.

---

## Yazılımcı Notları — Kontrol Listesi

### 1. GAM API Test

Gerçek bir publisher'ın gerçek GAM ID'si ile sistemin doğru çalışıp çalışmadığını kontrol et:

- [ ] `gam_client.py` ile GAM API'ye başarılı bağlantı
- [ ] Belirli bir path altındaki ad unit'lerin doğru çekilmesi
- [ ] Slot parse regex'inin gerçek pattern'lara uyması
- [ ] Max version hesaplamasının doğru olması

### 2. MAX API Test

- [ ] Gerçek management key ile ad unit'lerin çekilmesi
- [ ] Waterfall'daki ad unit'lerin slot bilgisinin doğru parse edilmesi
- [ ] POST `/ad_unit/{id}` ile güncelleme
- [ ] Verify GET'in doğru çalışması

### 3. End-to-End Senaryo

- [ ] Publisher ekle → App ekle → Dry Run → Onayla → Run → Verify → Rollback

### 4. PostgreSQL

- [ ] Railway PostgreSQL servisi aktif
- [ ] `DATABASE_URL` bağlantısı çalışıyor
- [ ] Tablolar init'de oluşuyor
- [ ] FK cascade'leri çalışıyor

### 5. Scheduler

- [ ] Günlük 03:00 slot cache sync çalışıyor
- [ ] 30+ gün eski snapshot'lar temizleniyor
- [ ] Hybrid mod dry run'ları çalışıyor ve email gönderiyor

### 6. Güvenlik

- [ ] `management_key`'ler DB'de plaintext — encryption düşünülebilir
- [ ] `GAM_SERVICE_ACCOUNT_JSON` sadece Railway env'de, git'te yok
- [ ] JWT secret production'da güçlü
- [ ] API key'ler response'larda maskeli

---

## Rate Limits & Performance

### AppLovin MAX API
- **2000 istek/saat**
- 1700 ad unit → ~17 GET (pagination) + ~N POST + ~N GET (verify)
- Run'lar background thread'de, blocking değil

### Google Ad Manager API
- Quota: 1000 QPS (yüksek)
- Makroo'nun kotası kullanılıyor
- Slot cache günlük sync ile gereksiz sorgu azaltılır

---

## Bilinen Kısıtlamalar

1. **In-memory job tracker** — Aktif job'lar `api.py`'deki dict'te. Sunucu restart olursa çalışan job'ların durumu kaybolur. Redis veya DB-backed job queue ileride eklenebilir.
2. **Scheduler tek instance** — Birden fazla instance çalışırsa scheduler duplicate çalışır. Railway'de tek instance yeterli.
3. **Email template inline** — `mailer.py`'de HTML string. Jinja2'ye taşınabilir.
4. **GAM SDK cold start** — İlk GAM çağrısı biraz yavaş (service account auth). Sonrakiler hızlı.

---

## Geliştirme Planı

- [x] **Faz 0:** Altyapı (auth, theme, Railway deploy)
- [ ] **Faz 1:** Yeni sistem — App bazlı, GAM entegrasyonu, slot karşılaştırma (yapılıyor)
- [ ] **Faz 2:** Hibrit mod tam otomatik (slot cache + scheduler + email)
- [ ] **Faz 3:** Opsiyonel iyileştirmeler (rollback UI, slot sync history, per-publisher kotası yönetimi)
