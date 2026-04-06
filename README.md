# ADSYIELD Refresh Tool

AppLovin MAX waterfall'unda GAM (Google Ad Manager) ad unit'lerinin otomatik güncellenmesini sağlayan dahili araç.

---

## Bu Proje Ne Yapıyor?

Makroo (MCM partner), bağlı olduğu yayıncılara GAM üzerinden çeşitli ad type ve CPM price'larla ad unit'ler veriyor. Yayıncılar bu ad unit'leri AppLovin MAX waterfall'larına ekliyor.

Belirli aralıklarla bu ad unit'lerin **refresh edilmesi** (versiyon güncellenmesi) gerekiyor. Örneğin GAM'deki line item ID'si `makroo_thegameops_banner_v45_1.50` ise, refresh sonrası `makroo_thegameops_banner_v46_1.50` olması gerekiyor.

Bu tool, waterfall'daki **sadece Makroo'ya ait** ad unit'leri bulup ID'lerindeki versiyon string'ini değiştiriyor. Diğer ad network'lere (IronSource, Unity, AdMob vs.) dokunmuyor.

### Temel Kavramlar

| Terim | Açıklama |
|---|---|
| **Publisher** | Makroo'nun ad unit verdiği yayıncı (ör: TheGameOps) |
| **Management Key** | Yayıncının AppLovin MAX API erişim anahtarı |
| **Publisher Tag** | Makroo'nun ad unit ID'lerinde kullandığı tanımlayıcı (ör: `thegameops`) |
| **Find String** | Waterfall'da aranacak mevcut versiyon (ör: `_v45_`) |
| **Replace String** | Yerine yazılacak yeni versiyon (ör: `_v46_`) |
| **Dry Run** | Waterfall'a dokunmadan sadece eşleşmeleri raporlayan test çalıştırma |
| **Canlı Run** | Gerçek değişiklikleri yapan ve doğrulayan çalıştırma |

---

## Mimari

```
┌──────────────────────────────────────────────────┐
│                    Railway                        │
│                                                  │
│  ┌─────────────┐     ┌──────────────────────┐   │
│  │  React UI   │────▶│   FastAPI Backend     │   │
│  │  (build/)   │     │   Port 8000           │   │
│  │             │     │                       │   │
│  │  - Login    │     │  api.py    → Router   │   │
│  │  - Publishers│     │  engine.py → Motor    │   │
│  │  - Approvals│     │  database.py → DB     │   │
│  │  - Job Logs │     │  scheduler.py → Cron  │   │
│  │             │     │  mailer.py → Email    │   │
│  └─────────────┘     │  auth.py  → JWT Auth  │   │
│                      └──────────┬─────────────┘   │
│                                 │                 │
│                      ┌──────────▼──────────┐     │
│                      │   SQLite (adsyield.db)│     │
│                      └─────────────────────┘     │
└──────────────────────────────────────────────────┘
                          │
                          ▼
              AppLovin MAX Management API
              https://o.applovin.com/mediation/v1
```

### Teknoloji

- **Backend:** Python 3.12 + FastAPI + Uvicorn
- **Frontend:** React 19 (build edilmiş static dosyalar, FastAPI tarafından serve ediliyor)
- **Database:** SQLite (WAL mode, thread-safe)
- **Auth:** JWT token (24 saat geçerlilik)
- **Deploy:** Railway (Docker, tek servis)

### Dosya Yapısı

```
├── api.py              # FastAPI ana dosyası — tüm endpoint'ler /api/ altında
├── engine.py           # AppLovin MAX API ile iletişim — ad unit tarama ve güncelleme
├── database.py         # SQLite veritabanı işlemleri
├── scheduler.py        # Hybrid mod için zamanlayıcı (background thread)
├── mailer.py           # Email gönderim modülü (Gmail SMTP)
├── auth.py             # JWT authentication — login, token doğrulama, middleware
├── requirements.txt    # Python bağımlılıkları
├── Dockerfile          # Multi-stage build (Node + Python)
├── .env.production     # React production ortam değişkenleri
├── src/                # React kaynak kodları
│   ├── api.js          # Frontend API client — tüm backend çağrıları
│   ├── App.js          # Ana uygulama — routing, tema, auth kontrolü
│   ├── App.css         # Tema sistemi (CSS custom properties)
│   └── components/
│       ├── Login.js        # Giriş sayfası
│       ├── PublisherList.js # Publisher listesi + Run/Dry Run
│       ├── PublisherForm.js # Publisher ekleme/düzenleme formu
│       ├── ApprovalList.js  # Hibrit mod onay sayfası
│       └── LogViewer.js     # İşlem logları
└── public/             # Static dosyalar (favicon, index.html)
```

---

## Çalışma Prensipleri

### FAZ 1 — Manuel Mod (Aktif)

Şu an production'da çalışan mod. Account manager (AM) tüm işlemleri manuel yapar.

```
AM giriş yapar
    │
    ▼
Publisher ekler (name, management_key, publisher_tag, find_string, replace_string)
    │
    ▼
"Dry Run" basar → Waterfall'a DOKUNMADAN eşleşmeleri gösterir
    │
    ▼
Sonuçları inceler (kaç ad unit eşleşti, hangileri değişecek)
    │
    ▼
"Run" basar → Gerçek değişiklikler yapılır + doğrulanır
    │
    ▼
Job Logs'dan sonuçları takip eder
```

**Teknik akış (engine.py):**

1. `GET /ad_units?fields=ad_network_settings` ile tüm ad unit'ler çekilir (100'er 100'er pagination)
2. Her ad unit'in `ad_network_settings` array'i taranır
3. Network adında `GOOGLE` geçen her entry kontrol edilir (`GOOGLE_AD_MANAGER_NETWORK`, `GOOGLE_AD_MANAGER_NATIVE_NETWORK` vb.)
4. Her entry'nin `ad_network_ad_unit_id` field'ında `publisher_tag` + `find_string` birlikte aranır
5. Eşleşme varsa:
   - **Dry Run:** Sadece loglanır, waterfall'a dokunulmaz
   - **Canlı Run:** Tüm eşleşen entry'ler güncellenir, `POST /ad_unit/{id}` ile yazılır
6. Write sonrası `GET /ad_unit/{id}` ile doğrulama yapılır — yeni ID gerçekten yazıldı mı kontrol edilir
7. Her operasyon `job_logs` tablosuna kaydedilir (SUCCESS, FAILED, DRY_RUN)

**Önemli:** Bir ad unit'te birden fazla eşleşme varsa tek POST atılır — tüm eşleşmeler aynı istekte güncellenir.

### FAZ 2 — Hibrit Mod (Altyapısı Hazır, Entegrasyon Bekliyor)

Hibrit modda AM'in yapacağı tek iş email'deki onay butonuna basmak. Sistem gerisini halleder.

```
Makroo yeni versiyonları hazırlar
    │
    ▼
[BEKLİYOR] Sistem Makroo'nun veri kaynağını kontrol eder
    │         (Google Sheet / Excel / API — henüz bağlanmadı)
    │
    ▼
Scheduler otomatik DRY RUN çalıştırır
    │
    ▼
Sonuç AM'e email ile gönderilir
    │
    ┌───────────────────────────────────────┐
    │  ADSYIELD — Dry Run Raporu            │
    │                                       │
    │  Publisher: TheGameOps                │
    │  Taranan ad unit: 847                 │
    │  Eşleşme: 23                          │
    │  Find: _v45_ → Replace: _v46_         │
    │                                       │
    │  [Sonuçları Gör ve Onayla]            │
    └───────────────────────────────────────┘
    │
    ▼
AM linke tıklar → UI'da Approvals sayfası açılır
    │
    ▼
Dry run detaylarını inceler (hangi ad unit, eski ID → yeni ID)
    │
    ▼
"Confirm Run" basar → Canlı run tetiklenir
    │
    ▼
48 saat içinde onaylanmazsa → Otomatik expire olur, bir şey yapılmaz
```

**Hibrit modun çalışması için eksik olan parça:**

Şu an `find_string` ve `replace_string` değerlerini AM formdan elle giriyor. Hibrit modda bunların otomatik güncellenmesi lazım. Makroo yeni versiyonlu ad unit'leri hazırladığında sistem bunu bir yerden öğrenmeli.

**Seçenekler:**
- Makroo tek bir Google Sheet'te tüm yayıncıların güncel versiyon bilgisini tutar → Sistem Google Sheets API ile okur
- Makroo bir API endpoint sunar → Sistem periyodik olarak sorgular
- Otomatik versiyon artırma (eğer pattern her zaman `_vXX_` formatındaysa) → `_v45_` başarılı olunca otomatik `_v46_` → `_v47_` olur

Bu karar Makroo'nun yazılımcısı ile birlikte verilmeli.

---

## Veritabanı Şeması

### publishers

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INTEGER PK | Otomatik artan ID |
| name | TEXT | Yayıncı adı |
| management_key | TEXT | AppLovin MAX API anahtarı |
| publisher_tag | TEXT | Ad unit ID'lerdeki tanımlayıcı string |
| find_string | TEXT | Aranacak string (ör: `_v45_`) |
| replace_string | TEXT | Yerine yazılacak string (ör: `_v46_`) |
| frequency_days | INTEGER | Refresh sıklığı (gün) — hibrit modda kullanılır |
| mode | TEXT | `manual` veya `hybrid` |
| notify_email | TEXT | Hibrit modda bildirim gidecek AM email'i |
| active | INTEGER | 1 = aktif, 0 = deaktif |
| last_run | TEXT | Son çalışma tarihi (ISO format) |
| created_at | TEXT | Oluşturulma tarihi |

### job_logs

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INTEGER PK | Otomatik artan ID |
| publisher_id | INTEGER FK | İlgili publisher |
| publisher_name | TEXT | Publisher adı (denormalize) |
| ad_unit_id | TEXT | AppLovin ad unit ID'si |
| ad_unit_name | TEXT | Ad unit adı |
| old_value | TEXT | Eski ad_network_ad_unit_id |
| new_value | TEXT | Yeni ad_network_ad_unit_id |
| status | TEXT | `SUCCESS`, `FAILED`, `DRY_RUN` |
| error_message | TEXT | Hata detayı (varsa) |
| ran_at | TEXT | İşlem tarihi |

### pending_approvals

| Kolon | Tip | Açıklama |
|---|---|---|
| id | INTEGER PK | Otomatik artan ID |
| publisher_id | INTEGER FK | İlgili publisher |
| job_id | TEXT UNIQUE | Benzersiz iş tanımlayıcısı |
| matched | INTEGER | Eşleşen ad unit sayısı |
| skipped | INTEGER | Atlanan ad unit sayısı |
| status | TEXT | `pending`, `approved`, `expired` |
| created_at | TEXT | Oluşturulma tarihi |
| expires_at | TEXT | Son geçerlilik (48 saat) |
| approved_at | TEXT | Onay tarihi |

---

## API Endpoint'leri

Tüm endpoint'ler `/api/` prefix'i altında. `/api/login` hariç hepsi JWT token gerektirir.

Header: `Authorization: Bearer <token>`

### Auth
| Method | Endpoint | Açıklama |
|---|---|---|
| POST | `/api/login` | Email + şifre ile giriş, JWT token döner |

### Publishers
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/publishers` | Tüm publisher'ları listele (key maskeli) |
| POST | `/api/publishers` | Yeni publisher ekle |
| PUT | `/api/publishers/{id}` | Publisher güncelle |
| DELETE | `/api/publishers/{id}` | Publisher sil (loglar da cascade silinir) |

### Run
| Method | Endpoint | Açıklama |
|---|---|---|
| POST | `/api/publishers/{id}/run?dry_run=true` | Dry run veya canlı run başlat — hemen `job_id` döner |
| GET | `/api/jobs/{job_id}` | İş durumunu sorgula (polling) |

### Approvals
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/approvals` | Bekleyen onayları listele |
| GET | `/api/approvals/{job_id}` | Onay detayı + dry run logları |
| POST | `/api/approvals/{job_id}/confirm` | Onayla → canlı run başlat |

### Logs
| Method | Endpoint | Açıklama |
|---|---|---|
| GET | `/api/logs` | Son 200 iş logu |

---

## Environment Variables

| Değişken | Zorunlu | Varsayılan | Açıklama |
|---|---|---|---|
| `JWT_SECRET` | **Evet** | `adsyield-dev-secret...` | Token imzalama anahtarı — production'da mutlaka değiştir |
| `CORS_ORIGINS` | Hayır | `http://localhost:3000` | İzin verilen origin'ler (virgülle ayrılmış) |
| `DB_PATH` | Hayır | `adsyield.db` | SQLite dosya yolu |
| `SMTP_HOST` | Hayır | `smtp.gmail.com` | Email sunucu adresi |
| `SMTP_PORT` | Hayır | `587` | Email sunucu portu |
| `SMTP_USER` | Hayır | — | Email gönderen hesap |
| `SMTP_PASS` | Hayır | — | Email hesap şifresi (Gmail App Password) |
| `APP_URL` | Hayır | `http://localhost:3000` | Email'deki linkler için uygulama URL'i |
| `JWT_EXPIRE_HOURS` | Hayır | `24` | Token geçerlilik süresi (saat) |

---

## Lokal Geliştirme

### Gereksinimler
- Python 3.9+
- Node.js 18+
- npm

### Kurulum

```bash
# Repo'yu klonla
git clone https://github.com/bugranalci/adsyield-refresher.git
cd adsyield-refresher

# Python ortamı
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Node bağımlılıkları
npm install

# Backend başlat (port 8000)
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Ayrı terminalde — Frontend başlat (port 3000)
npm start
```

Frontend `http://localhost:3000`, backend `http://localhost:8000` adresinde çalışır.

### Test Kullanıcıları

| Email | Şifre |
|---|---|
| `bnalci@adsyield.com` | `Adsyield-2026-*` |
| `ocakir@adsyield.com` | `Adsyield-2025-*` |

---

## Yazılımcının Kontrol Etmesi Gerekenler

### 1. Engine Mantığı — Gerçek Data ile Doğrulama

`engine.py` dosyasındaki `find_matches()` ve `apply_update()` fonksiyonları gerçek bir AppLovin management key ile test edilmeli.

**Kontrol noktaları:**

- `ad_network_settings` array'inin yapısı beklenen formatta mı? AppLovin API response'unun gerçek yapısı ile koddaki parsing uyumlu mu?
- `GOOGLE` string'i ile filtreleme yeterli mi? `GOOGLE_AD_MANAGER_NETWORK`, `GOOGLE_AD_MANAGER_NATIVE_NETWORK` dışında başka GOOGLE network key'i var mı?
- `ad_network_ad_unit_id` field'ı her zaman string mi? Null veya eksik olabilir mi?
- `POST /ad_unit/{id}` body'sindeki zorunlu alanlar (`id`, `name`, `platform`, `ad_format`, `package_name`, `ad_network_settings`) yeterli mi? AppLovin API ek alan gerektiriyor mu?
- Doğrulama (verify) mantığı: POST sonrası GET ile her `expected_new_id`'nin birebir kontrolü yapılıyor — bu yeterli mi?

**Test senaryosu:**
```
1. Gerçek key ile bir publisher ekle
2. Dry Run çalıştır — eşleşmeleri kontrol et
3. Eşleşen ID'ler gerçekten Makroo'nun koyduğu ID'ler mi?
4. Başka bir partner'ın ID'si yanlışlıkla eşleşiyor mu?
5. Canlı Run çalıştır — AppLovin dashboard'dan doğrula
```

### 2. AppLovin API Rate Limit

AppLovin MAX Management API saatte **2000 istek** limiti koyuyor.

- 1700 ad unit'lik bir publisher'da: 17 GET (pagination) + N POST (eşleşme sayısı kadar) + N GET (verify)
- Eğer 1700 ad unit'te 200 eşleşme varsa: ~17 + 200 + 200 = ~417 istek
- Tek publisher için sorun yok ama art arda birden fazla publisher çalıştırılırsa limite yaklaşılabilir
- `engine.py`'de rate limit (429) durumunda 60 saniye bekleme + max 5 retry var

**Kontrol:** Gerçek kullanımda bu limitlere yaklaşılıyor mu? Gerekirse `time.sleep()` süreleri artırılabilir.

### 3. SQLite ve Railway

**KRİTİK:** Railway'de filesystem **ephemeral** (geçici). Her deploy'da container yeniden oluşturulur ve SQLite dosyası **sıfırlanır**.

**Çözüm seçenekleri:**
- **Railway Volume Mount:** Railway dashboard'dan bir persistent volume oluşturup `/data` dizinine mount et. `DB_PATH=/data/adsyield.db` environment variable'ı ile SQLite'ı oraya yönlendir.
- **PostgreSQL'e geçiş:** Railway'de managed PostgreSQL servisi oluşturup `database.py`'yi `psycopg2` ile yeniden yaz. Daha sağlam ama daha fazla iş.

Volume mount en hızlı çözüm — Railway dashboard'dan 2 dakikada yapılır.

### 4. Güvenlik

- `management_key` veritabanında **plaintext** saklanıyor. Bu key'lerle waterfall'a yazma yetkisi var. Eğer DB'ye yetkisiz erişim olursa tüm key'ler açığa çıkar. Encryption eklenebilir.
- `auth.py`'deki default kullanıcı şifreleri kod içinde bcrypt hash olarak üretiliyor. Production'da kullanıcıları `AUTH_USERS` environment variable'ından almak daha güvenli.
- JWT secret production'da güçlü ve benzersiz olmalı.
- API endpoint'lerinde input validation minimum düzeyde — `find_string`, `replace_string` için uzunluk/karakter kontrolü yok.

### 5. Hata Senaryoları

Şu durumlar test edilmeli:

- AppLovin API erişilemezse (timeout, 500, 503) → Engine durur, hata loglanır mı?
- Geçersiz management key (401/403) → Anlamlı hata mesajı dönüyor mu?
- POST başarılı ama verify başarısız → Log'a `FAILED` yazılıyor mu?
- Aynı publisher için eşzamanlı iki Run → İkinci istek reddediliyor mu?
- Çok büyük waterfall (5000+ ad unit) → Timeout sorunu var mı?

---

## Yazılımcının Eklemesi Gerekenler

### 1. Railway Volume Mount (Öncelikli)

SQLite veritabanının deploy'lar arasında korunması için:

1. Railway dashboard → Servis → **Volumes** sekmesi
2. **Add Volume** → Mount path: `/data`
3. Environment variable ekle: `DB_PATH=/data/adsyield.db`
4. Redeploy

### 2. Makroo Veri Kaynağı Entegrasyonu (Faz 2 — Hibrit Mod)

Hibrit modun tam otomatik çalışması için Makroo'nun yeni ad unit versiyonlarını paylaştığı kaynağa bağlanılmalı.

**Yapılması gereken:**

1. Makroo'nun yazılımcısı ile görüşüp veri formatını belirle:
   - Google Sheet ise → Google Sheets API (service account) ile okuma
   - API ise → Periyodik sorgulama
   - Tek bir master Sheet mi, publisher bazlı ayrı Sheet'ler mi?

2. Yeni bir modül yaz (ör: `sheet_reader.py`):
   ```
   def get_latest_versions(publisher_id) -> dict:
       """Makroo'nun kaynağından güncel find/replace değerlerini çek"""
       return {
           "find_string": "_v46_",
           "replace_string": "_v47_"
       }
   ```

3. `scheduler.py`'deki `run_hybrid_check()` fonksiyonunu güncelle:
   - Publisher'ın mevcut `find_string`/`replace_string` değerlerini Makroo kaynağından al
   - Değişiklik varsa DB'yi güncelle
   - Sonra dry run çalıştır

4. Dry run başarılı olursa:
   - `pending_approvals` tablosuna kayıt oluştur
   - AM'e email gönder (`mailer.py` hazır)
   - AM onaylarsa canlı run tetiklenir (`api.py`'deki `/approvals/{job_id}/confirm` endpoint'i hazır)

### 3. Gmail SMTP Ayarları

Email bildirimleri için:

1. Bir Gmail hesabı belirle (ör: `notifications@adsyield.com`)
2. Google hesap ayarlarından **App Password** oluştur (2FA açık olmalı)
3. Railway Variables'a ekle:
   ```
   SMTP_USER=notifications@adsyield.com
   SMTP_PASS=xxxx-xxxx-xxxx-xxxx
   APP_URL=https://adsyield-refresher-production.up.railway.app
   ```

### 4. Custom Domain (Opsiyonel)

Hostinger DNS ayarlarından:
1. CNAME kaydı ekle: `refresh.adsyield.com` → `adsyield-refresher-production.up.railway.app`
2. Railway dashboard → Settings → Networking → Custom Domain → `refresh.adsyield.com`
3. Railway SSL sertifikasını otomatik oluşturacak

Sonra `APP_URL` environment variable'ını `https://refresh.adsyield.com` olarak güncelle.

### 5. Yeni Kullanıcı Ekleme

Şu an iki kullanıcı tanımlı. Yeni kullanıcı eklemek için:

**Seçenek A — Kod içi (basit):**
`auth.py` dosyasındaki `_load_users()` fonksiyonundaki default dict'e yeni satır ekle:
```python
"yeni@adsyield.com": bcrypt.hashpw(b"sifre", bcrypt.gensalt()).decode(),
```

**Seçenek B — Environment variable (daha güvenli):**
Railway Variables'a `AUTH_USERS` ekle:
```
AUTH_USERS=email1:bcrypt_hash1,email2:bcrypt_hash2
```
Hash üretmek için: `python3 -c "import bcrypt; print(bcrypt.hashpw(b'sifre', bcrypt.gensalt()).decode())"`

### 6. Loglama ve Monitoring (Önerilen)

- Railway dashboard'dan uygulama logları izlenebilir
- Uzun vadede Sentry veya benzeri bir error tracking servisi eklenebilir
- Scheduler'ın çalışıp çalışmadığını izlemek için basit bir health check endpoint'i eklenebilir

---

## AppLovin MAX API Referans

- **Base URL:** `https://o.applovin.com/mediation/v1`
- **Auth:** `Api-Key` header'ı ile management key
- **Rate Limit:** 2000 istek/saat
- **Kullanılan endpoint'ler:**
  - `GET /ad_units?fields=ad_network_settings&limit=100&offset=0` — Ad unit listesi
  - `GET /ad_unit/{id}?fields=ad_network_settings` — Tekil ad unit detayı
  - `POST /ad_unit/{id}` — Ad unit güncelleme

**Önemli:** AppLovin MAX API'de MCM (parent-child) erişim mekanizması yok. Her publisher'ın kendi management key'i gerekli. Makroo'nun kendi key'i ile child publisher'ların waterfall'una erişim mümkün değil.

---

## Bilinen Kısıtlamalar

1. **SQLite** — Tek sunucu için yeterli, ama horizontal scaling yapılamaz. Çok yoğun kullanımda PostgreSQL'e geçiş düşünülebilir.
2. **In-memory job tracker** — Aktif job'lar `api.py`'deki `jobs` dict'inde tutuluyor. Sunucu restart olursa çalışan job'ların durumu kaybolur. Uzun vadede Redis veya DB-backed job queue düşünülebilir.
3. **Scheduler tek instance** — Birden fazla instance çalıştırılırsa scheduler duplicate çalışır. Railway'de tek instance yeterli.
4. **Email template** — `mailer.py`'deki HTML template inline yazılmış. Jinja2 template'e taşınabilir.
