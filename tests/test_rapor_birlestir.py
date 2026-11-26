"""scripts/rapor_birlestir.py: şekil yolları ve eksik bölümler (YM-4)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rapor_birlestir", ROOT / "scripts" / "rapor_birlestir.py")
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)


def test_image_paths_are_rewritten_relative_to_report():
    src = ROOT / "docs" / "rapor"
    text, missing = rb.fix_images("![CC-CV](ym2-cc-cv.png) ![t](../raporlar/hafta5-ym2-tepe-yuk.png)", src)
    assert missing == []
    assert "](ym2-cc-cv.png)" in text and "](../raporlar/hafta5-ym2-tepe-yuk.png)" in text


def test_missing_image_becomes_visible_note():
    text, missing = rb.fix_images("![Yok](olmayan.png)", ROOT / "docs" / "rapor")
    assert missing == ["olmayan.png"] and "Şekil bekleniyor" in text


def test_section_title_is_dropped_and_cut_applies(tmp_path):
    f = tmp_path / "b.md"
    f.write_text("# Kendi başlığım\n\nmetin\n\n## 6. Sunum için notlar\ngizli\n", encoding="utf-8")
    body = rb.section_body(f, "## 6. Sunum için notlar")
    assert body == "metin"


def test_every_section_has_owner_and_path():
    for title, owner, rel, _, _ in rb.BOLUMLER:
        assert title and owner and rel.startswith("docs/")
