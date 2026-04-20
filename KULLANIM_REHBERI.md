# ADSYIELD Refresh Tool — Account Manager Kullanım Rehberi

Bu rehber, sistemin nasıl kullanılacağını adım adım anlatır. Hiç teknik bilgi gerektirmez.

---

## Sistem Ne İşe Yarıyor?

Makroo, yayıncılara GAM üzerinden ad unit'ler veriyor. Bu ad unit'lerin belirli aralıklarla yeni versiyonlara geçirilmesi gerekiyor (ör: `V7_bnr_aos_5.50` → `V8_bnr_aos_5.50`).

Eskiden bu işlemi manuel yapıyordun — her yayıncının waterfall'una tek tek girip ID'leri güncelleyerek. Bu tool sayesinde:

1. Sistem Makroo'nun GAM hesabından yeni versiyonları otomatik tespit ediyor
2. Yayıncının MAX waterfall'undaki eski versiyonlarla karşılaştırıyor
3. Sana "şunlar değişecek" diye bir rapor gösteriyor
4. Sen onaylarsan sistem otomatik güncelliyor ve her değişikliği doğruluyor

**Kısacası:** Elinle yaptığın refresh işini sistem yapıyor, sen sadece onay veriyorsun.

---

## Giriş

1. Tarayıcıda sistemin adresini aç: `https://adsyield-refresher-production.up.railway.app`
2. Login ekranında kendi email'in ve şifren ile giriş yap:
   - `bnalci@adsyield.com` / `Adsyield-2026-*`
   - `ocakir@adsyield.com` / `Adsyield-2025-*`
3. Giriş yaptıktan sonra ana sayfada **Publishers** tab'ını göreceksin

**Sağ üstte:**
- Email adresin (kim giriş yapmış)
- **Cikis** butonu
- Güneş/Ay ikonu → tema değiştirme (light/dark)

---

## Ekran Yapısı

Sistemde 3 ana sayfa var:

| Tab | Ne İşe Yarar |
|---|---|
| **Publishers** | Yayıncılar ve oyunları (app'leri) burada |
| **Approvals** | Hibrit modda sistem senin onayını bekliyor (sadece hibrit mod kullanılırsa) |
| **Job Logs** | Tüm geçmiş işlemlerin kaydı ve Rollback butonları |

---

## Temel Kavramlar

**Publisher (Yayıncı):** Bir AppLovin MAX hesabı. Her yayıncının bir Management Key'i ve bir GAM Publisher ID'si var. Örnek: Mackolik.

**App (Oyun/Uygulama):** Yayıncının oyunu/uygulaması. Her platform ayrı app sayılır — **Mackolik AOS** ve **Mackolik iOS** iki ayrı app'tir.

**Slot:** Bir app içindeki ad unit tipi/fiyat kombinasyonu. Örnek slot'lar:
- `bnr_aos_5.50` (banner, android, $5.50 CPM)
- `int_aos_55.00` (interstitial, android, $55.00 CPM)
- `mrec_aos_7.50` (mrec, android, $7.50 CPM)

**Version:** Slot'un versiyon numarası. Makroo zaman zaman yeni versiyon çıkarır (V7 → V8).

---

## Adım 1: Yayıncı (Publisher) Ekleme

İlk defa bir yayıncıyı sisteme ekliyorsan:

1. **Publishers** tab'ında **+ Add Publisher** butonuna bas
2. Açılan formu doldur:

| Alan | Ne Yazacaksın | Örnek |
|---|---|---|
| **Publisher Name** | Yayıncının adı | `Mackolik` |
| **Management Key** | Yayıncının AppLovin MAX API anahtarı | `e0757bd737fa69...` |
| **GAM Publisher ID** | Makroo'nun sana verdiği GAM numarası | `22860626436` |
| **Mode** | Manuel veya Hibrit | `Manual` (ilk başta) |

3. **Save Publisher** butonuna bas

**Dikkat edilecekler:**
- **Management Key'i** yayıncıdan alırsın — AppLovin MAX dashboard'ının Account > Keys bölümünde bulunuyor
- **GAM Publisher ID** her yayıncı için farklı — Makroo'dan veya GAM path'inden öğrenebilirsin (path'te `/324749355,XXXXXXX/` kısmının ikinci sayısı)
- **Mode:** Manual ile başla, güvendikten sonra Hybrid'e çevirebilirsin

---

## Adım 2: App (Oyun) Ekleme

Yayıncıyı ekledikten sonra o yayıncının oyunlarını eklemen gerekiyor.

1. Publishers listesinde yayıncının adına veya **Apps** butonuna tıkla
2. Açılan sayfada **+ Add App** butonuna bas
3. Formu doldur:

| Alan | Ne Yazacaksın | Örnek |
|---|---|---|
| **Label** | UI'da görünecek isim | `Mackolik AOS` |
| **GAM App Name** | GAM path'indeki klasör adı (birebir aynı) | `Mackolik` |
| **Platform** | Android veya iOS | `Android (aos)` |

4. **Save App** butonuna bas

**Önemli:** Bir yayıncının birden fazla oyunu varsa her birini ayrı ayrı ekle. Aynı oyunun hem Android hem iOS versiyonu varsa, ikisi de ayrı app olarak eklenir (`Mackolik AOS` ve `Mackolik iOS`).

**GAM App Name'i nereden bulacağım?**
GAM path'inde: `/324749355,22860626436/2021/Mackolik/V8_bnr_aos_5.50`
Burada `Mackolik` olan kısım GAM App Name. Büyük/küçük harf duyarlı, birebir yazmalısın.

---

## Adım 3: App Detayına Girme

App'i ekledikten sonra satırına tıklarsan o app'in detay sayfası açılır. Burada göreceklerin:

- **App bilgileri:** Label, GAM App Name, Platform
- **Slot Status tablosu:** GAM'de bu app için olan tüm slot'lar ve max versiyonları
- **Dry Run** butonu
- **Run** butonu

İlk defa açtığında **Slot Status boş olacak** — çünkü sistem henüz GAM'e bakmamış. Bir kere Dry Run yapınca slot cache dolacak ve sonraki ziyaretlerinde direkt göreceksin.

---

## Adım 4: Dry Run

**Dry Run nedir?** Sistem GAM'e bakar, MAX'e bakar, karşılaştırır ve "şunlar değişmesi lazım" diye rapor üretir — **ama hiçbir değişiklik yapmaz.** Tamamen güvenli bir test.

**Nasıl yapılır:**

1. App detay sayfasında **Dry Run** butonuna bas
2. Buton "GAM ve MAX taraniyor..." yazısına döner (yaklaşık 10-30 saniye)
3. Bittiğinde bir popup açılır:
   ```
   DRY-RUN tamamlandi
   Basarili: 23
   Hatali: 0
   Atlanan: 847
   ```

**Ne anlama geliyor?**
- **Basarili 23:** 23 tane ad unit'te yeni versiyona geçecek değişiklik var
- **Hatali 0:** Hiçbir hata yok
- **Atlanan 847:** MAX waterfall'daki diğer 847 ad unit bu app'e ait değil (başka network'ler, başka publisher'lar vs.)

**Dry Run sonrası:**
- Slot Status tablosu doldu — GAM'deki max versiyonları görüyorsun
- **Job Logs** tab'ına gidersen, her eşleşen ad unit'in eski ID'si ve yeni ID'si listeleniyor (`DRY_RUN` etiketiyle)

---

## Adım 5: Canlı Run (Gerçek Değişiklik)

Dry Run sonucunu inceledikten ve mantıklı olduğuna emin olduktan sonra gerçek değişikliği yap.

1. App detay sayfasında **Run** butonuna bas
2. "`Mackolik AOS` icin CANLI RUN baslatilacak. Emin misiniz?" diye onay ister — **Tamam**
3. Sistem çalışıyor: MAX API'ye POST atıyor, her değişikliği doğruluyor
4. Bittiğinde popup:
   ```
   CANLI tamamlandi
   Basarili: 23
   Hatali: 0
   Atlanan: 847
   ```

**Arka planda ne oluyor?**
- Her değişiklik öncesi otomatik **snapshot** alınıyor (rollback için)
- MAX waterfall güncelleniyor
- Her güncelleme MAX API'den tekrar okunup doğrulanıyor
- Tüm işlemler Job Logs'a kaydediliyor (`SUCCESS` veya `FAILED`)

---

## Adım 6: Job Logs — Geçmişi Görmek

**Job Logs** tab'ına gittiğinde şunları göreceksin:

| Kolon | Anlamı |
|---|---|
| Time | İşlem zamanı |
| Publisher | Hangi yayıncı |
| App | Hangi app |
| Ad Unit | MAX'teki ad unit adı |
| Old | Eski ID |
| New | Yeni ID |
| Status | `SUCCESS` / `FAILED` / `DRY_RUN` / `ROLLED_BACK` |
| Action | Rollback butonu (sadece başarılı değişiklikler için) |

**Status'lar:**
- `SUCCESS` (yeşil): Gerçek değişiklik başarıyla yapıldı
- `FAILED` (kırmızı): Bir hata oluştu — detayı görmek için teknik ekibe sor
- `DRY_RUN` (sarı): Sadece test, değişiklik yok
- `ROLLED_BACK` (gri): Önceden başarılıydı, sonra geri alındı

---

## Adım 7: Rollback (Geri Alma)

Bir değişiklik yanlış gitti veya hata vermedi ama istemediğin bir sonuç oluştu? Tek bir ad unit'i eski haline döndürebilirsin.

**Nasıl yapılır:**

1. **Job Logs** tab'ına git
2. Geri almak istediğin `SUCCESS` satırını bul
3. En sağdaki **Rollback** butonuna bas
4. "Bu ad unit'i eski haline dondurmek istiyor musun?" onayını ver
5. Sistem MAX'e POST atıp eski ID'yi geri yazar
6. Log'da o satır `ROLLED_BACK` olur, yeni bir log satırı oluşur

**Önemli:**
- **Her ad unit tek tek** rollback edilir — toplu geri alma yok (güvenlik için)
- Rollback yapabilmek için o işlemin **snapshot'ı** olmalı (otomatik alınıyor)
- Snapshot'lar **30 gün** saklanır, sonra otomatik silinir
- Rollback edilmiş bir satırı tekrar rollback edemezsin

---

## Günlük İş Akışı Örneği

**Senaryo:** Mackolik yayıncısının Android oyununda yeni versiyonlar çıktı, refresh etmen lazım.

1. Sisteme giriş yap
2. Publishers → Mackolik'e tıkla
3. Mackolik AOS app'ine tıkla
4. **Dry Run** butonuna bas → sonucu incele (ör: 23 değişiklik görünüyor)
5. Değişiklikler mantıklıysa **Run** butonuna bas → onay ver
6. İşlem tamamlanınca Job Logs'dan sonuçları kontrol et
7. Bir sorun olursa o ad unit'i rollback et

**Bu kadar. Toplam süre: 2-3 dakika.**

---

## Hibrit Mod (İleri Kullanım)

Hibrit mod, sistemin günlük olarak otomatik Dry Run yapıp sana email atmasını sağlar. Sen sadece email'deki linkten onay verirsin.

**Şu an devrede değil** — Gmail SMTP ayarları ve Makroo entegrasyonu tamamlanınca aktif olacak. İlk faz olarak **manuel mod** ile başla, sistem stabilleştikten sonra hibrit'e geçersin.

**Hibrit'e geçiş için:**
- Publisher'ı Edit et → Mode'u `Hybrid` yap → Notify Email gir
- Artık bu publisher için sistem her gün 03:00'da kontrol edip gerekiyorsa dry run yapar ve sana email atar
- Email'deki "Sonuclari Gor ve Onayla" linkine basarsan **Approvals** tab'ında detay açılır
- Orada **Confirm Run** butonu ile canlı run'ı tetiklersin
- 48 saat içinde onaylamazsan işlem expire olur (güvenlik için)

---

## Sık Karşılaşılan Durumlar

### "Eslesme bulunamadi" uyarısı

Dry Run sonucu boş — yani GAM'de yeni versiyon yok veya MAX waterfall zaten güncel. Endişelenme, her şey normal. Bir süre sonra tekrar dene.

### "App'in publisher'inda management_key veya gam_publisher_id eksik" hatası

Publisher'ı eklerken bu alanları doldurmayı unutmuşsun. Publisher listesinde **Edit** ile düzelt.

### "Bu app icin zaten bir job calisiyor" uyarısı

Aynı app için bir işlem devam ediyor, tekrar butona basma. Bitmesini bekle.

### Run sırasında uzun sürüyor

Normal. 1700 ad unit'lik bir waterfall'da işlem 5-10 dakika sürebilir. Sayfayı kapatma — işlem arka planda devam etmese de UI o sırada polling yapıyor.

### GAM hatası

`GAM hatasi: ...` şeklinde bir mesaj aldıysan, muhtemelen GAM Publisher ID yanlış veya Makroo'nun service account'unun o publisher'a erişimi yok. Bunu teknik ekiple konuş.

---

## Güvenlik Notları

- **Management Key'ler** sistemde saklanıyor ama UI'da maskeli görünüyor (`***abc123`)
- **Şifreni kimseyle paylaşma** — her AM kendi hesabıyla giriş yapmalı
- **Aynı anda birden fazla AM aynı app'te** çalışırsa sistem ikincisine "job zaten calisiyor" der, sorun olmaz
- **Canlı Run her zaman tek tek** — toplu işlem yok. Her app ayrı ayrı onaylanıp çalıştırılır

---

## Soru ve Sorunlar

Sistemde hata veya beklenmedik bir durum görürsen:

1. Ekran görüntüsü al
2. Hangi yayıncı/app üzerinde çalışıyorsan not et
3. Ne yaptığını adım adım yaz
4. Teknik ekibe ilet

Sistem deploy'da hata verirse `https://adsyield-refresher-production.up.railway.app` adresi bir süre açılmayabilir — 1-2 dakika bekle, Railway otomatik düzeltir.

---

İyi çalışmalar.
