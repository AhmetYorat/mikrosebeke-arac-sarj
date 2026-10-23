# Veri

Ham ve işlenmiş veri dosyaları repoya girmez (`.gitignore`). Her veri setinin nereden ve nasıl
indirildiğini YM-1 buraya yazar ki herkes aynı dosyaları üretebilsin.

| Veri | Kaynak | Konum |
| --- | --- | --- |
| Güneş ışınımı / PV üretimi | PVGIS | ham: `data/raw/pvgis_bandirma_2023.csv` (+ `.json`), temiz: `data/processed/pv_bandirma_2023.csv` |
| EV şarj oturumları | Caltech ACN-Data veya sentetik | `data/raw/acn_caltech_sample.json` |
| Tarife | EPDK üç zamanlı tarife | `config/default.yaml` |
| Yük profilleri (konut + ticari) | BDEW H0/G0 (demandlib) | `data/processed/yuk_profilleri_2023.csv` |

Formatlar, birimler ve dikkat edilecekler: [docs/veri-kaynaklari.md](../docs/veri-kaynaklari.md).

## İndirme

Sanal ortam açıkken (`source .venv/bin/activate`), repo kök klasöründen çalıştır.

**PVGIS** (anahtar gerekmez; konum ve yıl `config/default.yaml` içinden okunur). İndirir, temizler ve
`data/processed/` altına yazar:

```bash
python -m microgrid.data.pvgis
```

**Yük profilleri** (internet gerekmez; daire sayısı ve tüketimler `config/default.yaml → loads`):

```bash
python -m microgrid.data.loads
```

**ACN-Data** (ücretsiz token: https://ev.caltech.edu/register). Token'ı repoya yazma:

```bash
export ACN_API_TOKEN="buraya-token"
python -m microgrid.data.acn
```
