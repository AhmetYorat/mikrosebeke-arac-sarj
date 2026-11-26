"""Ekip bölümlerini tek rapor dosyasında birleştirir (YM-4).

    python scripts/rapor_birlestir.py            # docs/rapor/RAPOR.md (+ pandoc varsa RAPOR.docx)

Bölümler aşağıdaki BOLUMLER listesinin sırasıyla eklenir. Bir bölümün dosyası henüz yoksa yerine "bekleniyor"
kutusu konur; böylece rapor her an birleştirilebilir ve eksik olan açıkça görünür.

Her bölüm sahibinin kendi dosyasındadır; RAPOR.md'yi elle düzenlemeyin, bir sonraki birleştirmede kaybolur.
Şekiller: bölümdeki göreli yollar RAPOR.md'nin yerine göre düzeltilir. Entegrasyon bölümünün karşılaştırma şekilleri
`python -m microgrid.sim.sonuclar` çıktısından (results/sonuclar/) docs/rapor/sekiller/ altına kopyalanır.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "docs" / "rapor"
OUT = OUT_DIR / "RAPOR.md"

# (başlık, sorumlu, dosya, kesilecek başlık: bu başlıktan sonrası rapora girmez, editör notu)
BOLUMLER = [
    ("Giriş", "YM-4 (taslak)", "docs/rapor/giris.md", None, None),
    ("Veri ve Yöntem", "YM-1", "docs/rapor/ym1-veri-ve-yontem.md", None, None),
    ("Şarj İstasyonu Modeli", "YM-2", "docs/rapor/sarj-istasyonu.md", None, None),
    ("Enerji Yönetim Sistemi ve Optimizasyon", "YM-3", "docs/raporlar/hafta10-ym3-rapor-ems.md",
     "## 6. Sunum için notlar",
     "Bu bölümdeki sayılar YM-2'nin istasyon modeli birleşmeden önce, sahte istasyonla (CC-CV ve ünite paylaşımı yok) "
     "üretildi. Gerçek istasyonla güncel karşılaştırma *Entegrasyon ve Senaryo Karşılaştırması* bölümündedir; "
     "rapor teslim edilmeden önce bu bölümün sayıları onunla uyumlu hâle getirilmelidir."),
    ("Sistem Tasarımı, Şebeke ve Dinamik Analiz", "EM-1, EM-2", "docs/rapor/em-sebeke-ve-dinamik.md", None, None),
    ("Entegrasyon ve Senaryo Karşılaştırması", "YM-4", "docs/rapor/ym4-entegrasyon-ve-sonuclar.md", None, None),
    ("Sonuç", "YM-4 (taslak)", "docs/rapor/sonuc.md", None, None),
]

SEKILLER = {  # results/sonuclar/ -> docs/rapor/sekiller/
    "karsilastirma_haziran.png": "karsilastirma_haziran.png",
    "karsilastirma_aralik.png": "karsilastirma_aralik.png",
}

IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def copy_figures() -> list[str]:
    src = REPO / "results" / "sonuclar"
    dst = OUT_DIR / "sekiller"
    copied = []
    for name, target in SEKILLER.items():
        if (src / name).exists():
            dst.mkdir(exist_ok=True)
            shutil.copy2(src / name, dst / target)
            copied.append(target)
    return copied


def fix_images(text: str, source_dir: Path) -> tuple[str, list[str]]:
    """Görsel yollarını RAPOR.md'ye göre yeniden yazar; olmayan görselin yerine not koyar."""
    missing = []

    def repl(m: re.Match) -> str:
        alt, path = m.group(1), m.group(2)
        if path.startswith(("http://", "https://")):
            return m.group(0)
        target = (source_dir / path).resolve()
        if not target.exists():
            missing.append(path)
            return f"> *Şekil bekleniyor: {alt} (`{path}`)*"
        return f"![{alt}]({Path(os.path.relpath(target, OUT_DIR)).as_posix()})"

    return IMG.sub(repl, text), missing


def section_body(path: Path, cut: str | None) -> str:
    text = path.read_text(encoding="utf-8")
    if cut and cut in text:
        text = text[: text.index(cut)]
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):   # bölümün kendi başlığı; yerine numaralı başlık konur
        lines = lines[1:]
    return "\n".join(lines).strip()


def main() -> None:
    copied = copy_figures()
    parts = [
        "# Mikro-Şebeke Modellenmesi ve Analizi: Elektrikli Araç Şarj İstasyonu İçeren Sistem\n",
        "Akıllı Şebekeler dersi dönem projesi · Sunum: 24 Aralık 2026\n",
        f"*Bu dosya `scripts/rapor_birlestir.py` ile üretildi ({dt.date.today():%d.%m.%Y}). "
        "Elle düzenlemeyin; her bölüm kendi dosyasında düzenlenir.*\n",
    ]
    report = []
    for i, (title, owner, rel, cut, note) in enumerate(BOLUMLER, start=1):
        path = REPO / rel
        parts.append(f"\n# {i}. {title}\n\n*Sorumlu: {owner}*\n")
        if not path.exists():
            parts.append(f"> **Bölüm bekleniyor.** `{rel}` henüz repoda yok.\n")
            report.append((i, title, owner, "BEKLENİYOR", ""))
            continue
        if note:
            parts.append(f"> **Editör notu (YM-4):** {note}\n")
        body, missing = fix_images(section_body(path, cut), path.parent)
        parts.append(body + "\n")
        report.append((i, title, owner, "hazır", f"{len(missing)} şekil eksik" if missing else ""))

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"{OUT.relative_to(REPO)} yazıldı.")
    for i, title, owner, status, extra in report:
        print(f"  {i}. {title:42s} {owner:14s} {status} {extra}")
    if copied:
        print(f"  Şekiller kopyalandı: {', '.join(copied)}")
    else:
        print("  Karşılaştırma şekilleri yok: önce `python -m microgrid.sim.sonuclar` çalıştırın.")

    if shutil.which("pandoc"):
        docx = OUT.with_suffix(".docx")
        subprocess.run(["pandoc", OUT.name, "-o", docx.name, "--resource-path=.", "--toc", "--toc-depth=2",
                        "-M", "toc-title=İçindekiler"], cwd=OUT_DIR, check=True)
        print(f"{docx.relative_to(REPO)} yazıldı (pandoc).")
    else:
        print("pandoc yok: Word çıktısı üretilmedi (RAPOR.md yine de hazır).")


if __name__ == "__main__":
    main()
