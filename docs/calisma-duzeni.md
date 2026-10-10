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

## Perşembe raporu (1–2 sayfa)

- Bu hafta yapılanlar: kişi bazında kısa maddeler
- Kanıt: 1–2 grafik veya ekran görüntüsü
- Karşılaşılan sorunlar ve çözümler / hocaya sorulacak sorular
- Gelecek hafta planı

Raporlar `docs/raporlar/` altında tutulur.
