# Çalışma düzeni

## Haftalık döngü

| Gün | Ne yapılır? |
| --- | --- |
| Perşembe | Derste rapor. Ders sonrası 15–20 dk ekip toplantısı: hocanın geri bildirimi, haftanın görevlerinin teyidi |
| Cuma – Pazartesi | Görevler üzerinde çalışma |
| Pazartesi akşamı | Ara durum notu: herkes grupta 3 satır yazar (ne bitti, ne kaldı, nerede takıldım) |
| Salı | Takılan konular çözülür; entegrasyon gereken işler YM-4'e iletilir |
| **Çarşamba 18:00** | Çıktılar hazır: kod `main`'e birleşmiş; grafikler, ekran görüntüleri ve rapor bölümleri YM-4'e gönderilmiş |
| Çarşamba akşamı | YM-4 haftalık raporu birleştirir, demo bir kez çalıştırılıp kontrol edilir |

1 günden fazla takılan konu Pazartesi notunu beklemeden gruba yazılır.

29 Ekim resmî tatil: o hafta ders yok, rapor gruba yazılır ve 5 Kasım'da iki haftalık birlikte sunulur.

## Git akışı

1. Güncel `main`'den branch aç: `git switch main && git pull && git switch -c ym2/charging-station-v1`
   (isim: `rol/kısa-açıklama`).
2. Küçük ve sık commit at. Çalışırken `pytest` yeşil kalsın.
3. Push'la ve GitHub'da Pull Request aç. Açıklamaya ne yaptığını ve nasıl denediğini yaz.
4. YM-4 inceler ve birleştirir. `main`'e doğrudan push kapalıdır.
5. Çarşamba 18:00'e yetişmesi için PR'ı en geç Çarşamba öğlen aç.

Neden PR zorunlu: `main` her an demo edilebilir durumda kalmalı. Hoca derste canlı göstermemizi
isterse çalışan sürüm `main`'dir; yarım iş oraya girerse herkesin demosu bozulur.

## Elektrik ekibi için (Git kurmadan)

EM-1 ve EM-2'nin terminalden Git kullanması gerekmez; GitHub'ın web arayüzü yeterlidir.

Repoya girmesi gerekenler:

| Ne | Nereye | Kim |
| --- | --- | --- |
| Simulink CSV çıktıları | `simulink/outputs/` | EM-2 |
| Boyutlandırma ve ağ parametreleri (PV, BESS, hat, trafo) | `config/default.yaml` | EM-1, EM-2 |
| Tek hat şeması, parametre tablosu | `docs/` | EM-1 |

Dosya yükleme adımları:

1. GitHub'da ilgili klasörü aç, **Add file → Upload files** ile dosyayı sürükle.
   (Var olan bir dosyayı değiştirmek için dosyayı açıp kalem simgesine bas.)
2. Altta kısa bir açıklama yaz, **Create a new branch for this commit and start a pull request** seçeneğini işaretle.
3. **Propose changes**, ardından **Create pull request**. YM-4 inceleyip birleştirir.

CSV'leri WhatsApp'tan göndermeyin: hangisinin son sürüm olduğu karışır. Dashboard yalnızca repodaki dosyayı okur.

### Simulink modeli (`.slx`)

`.slx` ikili (binary) bir dosyadır; Git iki kişinin değişikliğini birleştiremez, son yükleyen diğerinin
işini ezer. Bu yüzden:

- Modelin çalışma kopyası elektrik ekibinin kendi ortak klasöründe durur ve aynı anda tek kişi düzenler
  (modelin o an kimde olduğu gruba yazılır).
- Repoya yalnızca kilometre taşlarında çalışan bir kopya konur (`simulink/`), commit açıklamasına
  hangi senaryoların çalıştığı yazılır.

## Perşembe raporu (1–2 sayfa)

- Bu hafta yapılanlar: kişi bazında kısa maddeler
- Kanıt: 1–2 grafik veya ekran görüntüsü
- Karşılaşılan sorunlar ve çözümler / hocaya sorulacak sorular
- Gelecek hafta planı

Raporlar `docs/raporlar/` altında tutulur.
