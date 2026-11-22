# Hafta 4 · YM-4 (Entegrasyon) · v0

## Bu hafta yapılanlar

- **v0 entegrasyonu incelendi.** YM-1'in v0 PR'ı (#8) döngüyü gerçek girdilerle (PVGIS + BDEW + EPDK) 24 saat
  uçtan uca çalıştırıyor. Döngü, sonuç tablosu ve pandapower bağlantısı Hafta 2–3'teki sözleşmeyle uyumlu;
  sonuçlar `results/v0_<gün>_steps.csv` ve `_station.csv` olarak yazılıyor. Sayılar için: [YM-1 Hafta 4 raporu](hafta4-ym1-raporu.md).
- **Veri yoksa sahte girdiye düşme (`sim/setup.py`).** Repoyu yeni klonlayan biri `python -m microgrid.data`
  çalıştırmadan döngüyü ya da dashboard'u açarsa hata almıyor. Sahte girdilerle çalışıyor ve bunu açıkça yazıyor;
  çıktı dosyaları da `mock_` önekiyle kaydediliyor ki raporda gerçek sonuçla karışmasın.
  Gerçek veri zorunluysa (`allow_mock=False`) sessizce sahteye düşmüyor.
- **Otomatik testler (CI).** `.github/workflows/testler.yml`: her PR'da ve `main`'e her birleştirmede `pytest`
  çalışıyor. CI PVGIS verisini kendisi indirip önbelleğe alıyor. Böylece yerelde atlanan gerçek veri testleri
  (v0, KPI) CI'da gerçekten çalışıyor. PR sayfasında yeşil tik yoksa birleştirilmiyor.

## Neden CI

YM-3'ün açık PR'ında (#3) bir test kırık (`pulp.LpVariable.dicts` yeni pulp sürümünde yok). Elle incelemede bu
gözden kaçabilirdi; CI ile PR sayfasında kırmızı görünür ve `main`'e girmeden yakalanır.

## Entegrasyon durumu

| Modül | Sorumlu | Durum |
| --- | --- | --- |
| Girdiler (PV, yük, tarife) | YM-1 | Gerçek, döngüye bağlı (PR #8) |
| Şarj istasyonu | YM-2 | **Döngüde değil.** Branch'teki sınıflar sözleşmedeki `requests/apply` arayüzünü uygulamıyor; döngü hâlâ `MockStation` kullanıyor |
| EMS + batarya | YM-3 | **Döngüde değil.** PR #3 sözleşmedeki `prepare/decide` arayüzünü uygulamıyor ve bir testi kırık |
| Şebeke (pandapower) | YM-4 + EM-2 | Döngüye bağlı; parametreler EM-2 doğrulaması bekliyor |

## Gelecek hafta

- Dashboard: senaryo seçimi ve istasyon görünümü (ünite doluluğu, araç SOC'leri).
