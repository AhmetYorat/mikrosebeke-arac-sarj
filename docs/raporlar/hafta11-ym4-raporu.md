# Hafta 11 · YM-4 (Entegrasyon) · Yedek demo kaydı, olası sorular

## Bu hafta yapılanlar

- **Yedek demo kaydı (`scripts/demo_kaydi.py`).** Dashboard'u açıyor, `docs/sunum/demo-akisi.md`'deki akışı
  kendiliğinden oynatıyor ve altına açıklama şeritleri koyarak ~2 dakikalık bir mp4 kaydediyor. Önbelleği kayıttan
  önce ayrı bir oturumda ısıttığı için videoda bekleme yok. **Gerçek veri yoksa kayıt yapmıyor**: sarı "sahte girdi"
  uyarılı bir video sunumda kullanılamaz. Betik bu ortamda sahte veriyle denendi (130 s, 1,8 MB; kareler kontrol edildi);
  gerçek kayıt YM-4'ün bilgisayarında, gerçek veriyle alınacak:

  ```bash
  pip install playwright && playwright install chromium   # bir kez
  python -m microgrid.data
  python scripts/demo_kaydi.py                             # -> docs/sunum/demo-yedek.mp4
  ```

- **Olası sorular (`docs/sunum/olasi-sorular.md`).** Proje geneli, istasyon, EMS, şebeke ve entegrasyon için soru ve
  cevaplar, her birinin sahibiyle. Sayılar yalnızca rapordaki gerçek veri tablolarından.

## Prova planı (herkes)

| Gün | Ne |
| --- | --- |
| 17 Aralık (Per) | Derste rapor ve sunum taslağına hocanın geri bildirimi |
| 21–22 Aralık | En az iki tam prova, süre tutarak (~20 dk + demo); olası sorular sırayla sesli cevaplanır |
| 23 Aralık (Çar) | Son düzeltmeler; demo-akisi.md'deki kontrol listesi; yedek videonun sunum bilgisayarında açıldığı kontrol edilir |
| 24 Aralık (Per) | Sunum |

## Sunumdan önce kapanması gerekenler

| | Sorumlu |
| --- | --- |
| Veri ve Yöntem bölümü için PR (`ym1/hafta9-duyarlilik`) | YM-1 |
| EMS bölümünün sayılarının gerçek istasyonla güncellenmesi | YM-3 |
| S3/S4 ünite sırası (4 araç hedefe yetişmiyor) | YM-3 |
| Sistem tasarımı, şebeke ve dinamik analiz bölümü; Simulink D1–D4 CSV'leri | EM-1, EM-2 |
| Giriş ve Sonuç taslaklarının onayı | Herkes |
| Gerçek veriyle yedek demo kaydı | YM-4 |
