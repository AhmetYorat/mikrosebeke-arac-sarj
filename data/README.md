# Veri

Ham ve işlenmiş veri dosyaları repoya girmez (`.gitignore`). Her veri setinin nereden ve nasıl
indirildiğini YM-1 buraya yazar ki herkes aynı dosyaları üretebilsin.

| Veri | Kaynak | Konum |
| --- | --- | --- |
| Güneş ışınımı / PV üretimi | PVGIS | `data/raw/pvgis_bandirma_2023.csv` (+ ham `.json`) |
| EV şarj oturumları | Caltech ACN-Data veya sentetik | `data/raw/acn_caltech_sample.json` |
| Tarife | EPDK üç zamanlı tarife | `config/default.yaml` |
| Yük profilleri | Açık veri seti veya sentetik | `data/raw/` |

Formatlar, birimler ve dikkat edilecekler: [docs/veri-kaynaklari.md](../docs/veri-kaynaklari.md).

## İndirme

Sanal ortam açıkken (`source .venv/bin/activate`), repo kök klasöründen çalıştır.

**PVGIS** (anahtar gerekmez; konum ve yıl `config/default.yaml` içinden okunur):

```bash
python -m microgrid.data.pvgis
```

**ACN-Data** (ücretsiz token: https://ev.caltech.edu/register). Token'ı repoya yazma:

```bash
export ACN_API_TOKEN="buraya-token"
python -m microgrid.data.acn
```
