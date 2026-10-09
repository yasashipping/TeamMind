# Faz 0 Spike Degerlendirme Kriterleri

Transkripti asagidaki sorularla puanlayin (her biri 1-5):

## 1. Anlasilabilirlik
- [ ] Cumleler dogal Turkce mi, kelime birlesme/bolme hatasi var mi?
- [ ] Rakamlar ve ozel isimler dogru mu? ("4.5 milyon", kisi adlari)

## 2. Islak Konusma Dayanikliligi
- [ ] Konusmacilar ust uste konusunca metin karismiyor mu?
- [ ] Gulusme, "eee", "hmm" gibi dolgu sesleri metne karismiyor mu?

## 3. Zamanlama
- [ ] Zaman damgalari gercek akisa yakin mi?

## 4. Halüsinasyon
- [ ] Hic soylenmemis seyler yazilmamis mi? (ozellikle sessiz bolumler)

## Karar
- Ortalama >= 4: large-v3 ile devam, diarization (whisperx) asamasina gec
- 3-4: medium/large-v3 karsilastir, VAD ayarlarini incele
- < 3: AssemblyAI/Deepgram API alternatifini degerlendir (kurumsal TR destegi daha iyi olabilir)
