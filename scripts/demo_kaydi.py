"""Canlı demonun yedek ekran kaydı (YM-4, Hafta 11).

Dashboard'u açar, `docs/sunum/demo-akisi.md`'deki akışı kendiliğinden oynatır ve video olarak kaydeder.
Sunumda dashboard açılmazsa bu video oynatılır.

Kurulum (bir kez):
    pip install playwright
    playwright install chromium
    python -m microgrid.data          # gerçek veri; yoksa kayıt yapılmaz

Kayıt:
    python scripts/demo_kaydi.py                  # -> docs/sunum/demo-yedek.mp4 (ffmpeg yoksa .webm)

Gerçek veri yoksa dashboard sarı "sahte girdi" uyarısı gösterir; böyle bir video sunumda kullanılamayacağı için
betik durur. Yalnızca betiği denemek için: --sahte-girdiye-izin-ver (çıktı adı "-SAHTE" ile biter).
"""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAHTE_UYARI = "sahte girdilerle"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_settled(page, timeout_ms: int = 300_000) -> None:
    """Streamlit'in hesaplaması bitene kadar bekle (spinner ve ilerleme çubuğu kaybolsun)."""
    page.wait_for_timeout(1200)
    for text in ("Simülasyon çalışıyor", "çalışıyor…"):
        page.wait_for_selector(f"text={text}", state="detached", timeout=timeout_ms)
    page.wait_for_timeout(1500)


def caption(page, text: str, seconds: float) -> None:
    """Videonun altına kısa bir açıklama şeridi koyar (sesli anlatım olmadan da anlaşılsın)."""
    page.evaluate(
        """([t]) => {
            let el = document.getElementById('demo-caption');
            if (!el) {
                el = document.createElement('div'); el.id = 'demo-caption';
                Object.assign(el.style, {position: 'fixed', left: '50%', bottom: '24px', transform: 'translateX(-50%)',
                    background: 'rgba(20,20,20,.86)', color: '#fff', padding: '12px 22px', borderRadius: '10px',
                    font: '500 20px system-ui, sans-serif', zIndex: 99999, maxWidth: '78%', textAlign: 'center'});
                document.body.appendChild(el);
            }
            el.textContent = t;
        }""",
        [text],
    )
    page.wait_for_timeout(int(seconds * 1000))


def scroll_main(page, pixels: int, steps: int = 12) -> None:
    """Fare tekerleğiyle yumuşak kaydırma. Streamlit ana alanı kendi içinde kaydığı için window.scrollBy işe yaramaz."""
    page.mouse.move(1000, 500)
    for _ in range(steps):
        page.mouse.wheel(0, pixels / steps)
        page.wait_for_timeout(110)
    page.wait_for_timeout(400)


def to_top(page) -> None:
    page.mouse.move(1000, 500)
    page.mouse.wheel(0, -20000)
    page.wait_for_timeout(500)


def open_scenario(page, base: str, code: str, day: str | None = None) -> None:
    page.goto(f"{base}/?senaryo={code}")
    page.wait_for_selector("text=Şebeke tepe alımı", timeout=300_000)
    wait_settled(page)
    if day:
        page.get_by_text(day, exact=True).click()
        wait_settled(page)


def tab(page, name: str) -> None:
    to_top(page)
    page.get_by_role("tab", name=name).click()
    wait_settled(page)


def record(base: str, out_dir: Path, allow_mock: bool) -> Path:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # 1) Önbelleği ısıt (kaydedilmez): karşılaştırma ilk seferde ~40 s sürer. Önbellek sunucu tarafında
        #    tutulduğu için kayıt oturumunda aynı ayarlar anında gelir.
        warm = browser.new_context(viewport={"width": 1600, "height": 900})
        page = warm.new_page()
        open_scenario(page, base, "S2")
        if page.get_by_text(SAHTE_UYARI).count() and not allow_mock:
            browser.close()
            sys.exit("Dashboard sahte girdiyle çalışıyor. Önce `python -m microgrid.data` çalıştırın.")
        for day in (None, "Aralik"):
            if day:
                page.get_by_text(day, exact=True).click(); wait_settled(page)
            tab(page, "Senaryo karşılaştırması")
            page.get_by_role("button", name="Bütün senaryoları çalıştır").click()
            page.wait_for_selector("text=KPI tablosunu indir", timeout=600_000)
        warm.close()

        # 2) Kayıt
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=1,
                                  record_video_dir=str(out_dir), record_video_size={"width": 1600, "height": 900})
        page = ctx.new_page()

        # --- Akış (docs/sunum/demo-akisi.md) ---
        open_scenario(page, base, "S2")
        caption(page, "S2 kontrolsüz şarj: 20 araç, 10 ünite. Akşam herkes aynı anda şarja takıyor.", 4)
        tab(page, "Güç akışları")
        scroll_main(page, 520)
        caption(page, "İstasyon (kırmızı) puant saatinde şebeke alımını site sınırının (kesikli) üstüne taşıyor.", 6)

        tab(page, "Şarj istasyonu")
        scroll_main(page, 520)
        caption(page, "Her satır bir ünite: 18:00'den sonra hepsi dolu ve tam güçte.", 5)
        scroll_main(page, 1100, 20)
        caption(page, "Araç başına geliş, bekleme, SOC ve hedefe ulaşma (YM-2 istasyon modeli).", 5)

        open_scenario(page, base, "S2")
        tab(page, "Şebeke")
        scroll_main(page, 520)
        caption(page, "Yük akışı (pandapower): en düşük gerilim ve trafo yüklenmesi.", 5)

        tab(page, "Senaryo karşılaştırması")
        if page.get_by_role("button", name="Bütün senaryoları çalıştır").count():   # yeni oturum: önbellekten anında
            page.get_by_role("button", name="Bütün senaryoları çalıştır").click()
        page.wait_for_selector("text=KPI tablosunu indir", timeout=600_000)
        scroll_main(page, 520)
        caption(page, "Altı senaryo aynı günde: akıllı şarj akşam tepesini ortadan kaldırıyor.", 6)
        caption(page, "Ama tepe sabaha kayıyor: optimizasyon şarjı gece tarifesinin bitişine (06:00) yığıyor.", 6)
        scroll_main(page, 700, 14)
        caption(page, "KPI tablosu: tepe, maliyet, verilen enerji, hedefe ulaşan araç, bekleme.", 7)

        open_scenario(page, base, "S6", day="Aralik")
        tab(page, "Şarj istasyonu")
        scroll_main(page, 520)
        caption(page, "S6 V2G, Aralık: mavi hücreler araçtan şebekeye. Araç %30'un altına inmiyor, ayrılışta hedef garanti.", 7)

        tab(page, "Dinamik (Simulink)")
        scroll_main(page, 400)
        caption(page, "Python günün kritik anını buluyor; elektrik ekibi o anı Simulink'te saniye mertebesinde inceliyor.", 6)

        video = page.video.path()
        ctx.close()
        browser.close()
    return Path(video)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cikti", default=str(REPO / "docs" / "sunum" / "demo-yedek"))
    ap.add_argument("--sahte-girdiye-izin-ver", action="store_true", help="yalnızca betiği denemek için")
    args = ap.parse_args()

    port = free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(REPO / "dashboard" / "app.py"), "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false"],
        cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    tmp = REPO / "results" / "demo_kaydi"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        time.sleep(6)
        webm = record(f"http://127.0.0.1:{port}", tmp, args.sahte_girdiye_izin_ver)
    finally:
        server.terminate()

    out = Path(args.cikti + ("-SAHTE" if args.sahte_girdiye_izin_ver else ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "26", "-preset", "veryfast", "-movflags", "+faststart", str(out.with_suffix(".mp4"))],
                       check=True)
        print(f"Kayıt: {out.with_suffix('.mp4')}")
    else:
        shutil.copy2(webm, out.with_suffix(".webm"))
        print(f"Kayıt: {out.with_suffix('.webm')} (ffmpeg yok, mp4'e çevrilmedi)")


if __name__ == "__main__":
    main()
