# MeetMind Mobil — Flutter iskeleti (Yol B: Google STT)

Basla-bitir kayit modeli. Telefon kaydeder, Supabase saklar, Cloud Run (Google STT + Claude) isler,
rapor telefona Realtime ile duser.

```
Flutter (Android+iOS)
  └─ kaydet (.m4a, 16 kHz mono) → Supabase Storage: recordings/<uid>/<id>.m4a
  └─ meetings satiri: status=uploaded
  └─ POST Cloud Run /process {meeting_id}  (Authorization: Bearer <Supabase JWT>)
Cloud Run (backend/)
  └─ Google Speech-to-Text v2 (chirp_2, tr-TR)   → transcript
  └─ app/pipeline/llm (segment → extract → filter) → report_md + items
  └─ meetings satiri: status=done, ses dosyasi silinir
Flutter
  └─ meetings.stream() ile durumu izler, raporu Markdown gosterir
```

## 1. Supabase
1. Yeni proje → SQL Editor → `supabase/schema.sql` calistir.
2. Authentication → Providers → Email acik (baslangic icin yeterli).
3. Settings → API'den al: `Project URL`, `anon key`, `service_role key`, `JWT Secret`.

## 2. Backend (Cloud Run)
Bu klasoru mevcut Python repo'nun koku altina `backend/` olarak koyun (yaninda `app/` olacak).
```
gcloud auth login && gcloud config set project <PROJE>
# sirlar
for s in anthropic-key supabase-url supabase-service-key supabase-jwt-secret; do gcloud secrets create $s --replication-policy=automatic; done
echo -n "$ANTHROPIC_API_KEY" | gcloud secrets versions add anthropic-key --data-file=-
# ... digerleri ayni sekilde
GOOGLE_CLOUD_PROJECT=<PROJE> bash backend/deploy.sh
```
Cikan URL'i Flutter'a `API_BASE` olarak verin.

**Gercek toplanti modu:** `stt_google.py` sesi GCS'e yukleyip `batch_recognize` ile isler
(saatlik kayit sorunsuz). GCS objesi is bitince silinir; bucket'ta ayrica 1 gunluk lifecycle var.
Cloud Run `--no-cpu-throttling` ile kurulur: `/process` hemen 202 doner, STT + Claude arka planda surer.
Islem sirasinda instance ayakta kalir (dakika basi ucret), is bitince tekrar sifira iner.

Konusmaci ayrimi: `STT_DIARIZE=1` ile deploy edin; transkript `i | K1 | metin` formatinda Claude'a gider
ve prompt'lardaki `Ahmet Yılmaz` alaniyla ayni pozisyona oturur (isimler yerine K1/K2 etiketleri).

## 3. Flutter
```
flutter create --org com.meetmind --project-name meetmind meetmind_app
# bu paketin lib/ ve pubspec.yaml'ini uzerine kopyalayin
flutter pub get
flutter run --dart-define=SUPABASE_URL=... --dart-define=SUPABASE_ANON_KEY=... --dart-define=API_BASE=https://meetmind-api-....run.app
```

### Android — `android/app/src/main/AndroidManifest.xml`
```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.INTERNET"/>
```
`android/app/build.gradle` → `minSdkVersion 23`.

### iOS — `ios/Runner/Info.plist`
```xml
<key>NSMicrophoneUsageDescription</key>
<string>Toplantıyı kaydedip rapor üretmek için mikrofon gerekir.</string>
```
Ekran kilitlenince kaydin kesilmemesi icin Xcode → Signing & Capabilities → Background Modes → **Audio** isaretleyin
(basla-bitir modelinde bile toplanti sirasinda telefon kilitlenir).

## Dosya haritasi
| Dosya | Gorev |
|---|---|
| `lib/services/recorder_service.dart` | Mikrofon izni, AAC kayit, basla/bitir |
| `lib/services/meeting_service.dart` | Storage yukleme, satir guncelleme, Cloud Run tetikleme, Realtime izleme |
| `lib/services/auth_service.dart` | Supabase e-posta girisi |
| `lib/screens/record_screen.dart` | KVKK onayi + sayac + Basla/Bitir |
| `lib/screens/report_screen.dart` | Ilerleme (3 adim) → Markdown rapor |
| `backend/server.py` | `/process` endpoint, JWT dogrulama, pipeline |
| `backend/stt_google.py` | `STTEngine` ile ayni arayuz, Google STT v2 |

## Ileride (bilerek disarida birakildi)
- Konusmaci etiketlerini (K1/K2) katilimci isimlerine eslestirme ekrani
- Aksiyon maddelerini ayri tablo yapip gorev takibi / takvim entegrasyonu
- Google OAuth girisi (Supabase provider olarak eklenir, kod degismez)
