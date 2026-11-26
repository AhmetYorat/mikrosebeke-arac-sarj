#!/bin/bash
# Mikro-şebeke projesi: kurulum + veri + dashboard (macOS). Çift tıklayınca Terminal'de çalışır.
cd "$(dirname "$0")" || exit 1
echo "== Proje klasörü: $(pwd)"

# 1) Python 3.10+ bul (macOS'un hazır Python'u 3.9, yetmez)
PY=""
for c in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
    PY="$(command -v "$c")"; break
  fi
done
if [ -z "$PY" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "== Python 3.10+ yok, Homebrew ile Python 3.12 kuruluyor (birkaç dakika sürebilir)..."
    brew install python@3.12 || { echo "Homebrew kurulumu başarısız."; read -r -p "Kapatmak için Enter"; exit 1; }
    PY="$(brew --prefix)/bin/python3.12"
  else
    echo "!! Python 3.10 veya üstü bulunamadı ve Homebrew yok."
    echo "   python.org'dan Python 3.12 macOS yükleyicisini kurup bu dosyaya tekrar çift tıklayın."
    open "https://www.python.org/downloads/macos/"
    read -r -p "Kapatmak için Enter"; exit 1
  fi
fi
echo "== Kullanılan Python: $PY ($("$PY" --version))"

# 2) Sanal ortam (eski 3.9 ortamı varsa temizlenip yeniden kurulur)
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
  echo "== Sanal ortam (.venv) oluşturuluyor..."
  "$PY" -m venv --clear .venv || { read -r -p "venv oluşturulamadı. Kapatmak için Enter"; exit 1; }
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
echo "== Paketler kuruluyor (ilk seferde birkaç dakika)..."
pip install -q -r requirements.txt && pip install -q -e . || { read -r -p "Paket kurulumu başarısız. Kapatmak için Enter"; exit 1; }

# 3) Gerçek veri (bir kez; varsa atlanır)
if [ -z "$(ls data/processed/*.csv 2>/dev/null)" ]; then
  echo "== Gerçek veri indiriliyor (PVGIS)..."
  python -m microgrid.data || echo "!! Veri hazırlanamadı; dashboard sahte girdiyle açılacak (üstte sarı uyarı)."
fi

# 4) Dashboard
echo "== Dashboard açılıyor: http://localhost:8501  (kapatmak için bu pencerede Ctrl+C)"
# Streamlit'in ilk açılıştaki "Email:" sorusunu atla (boş e-posta kaydı)
mkdir -p "$HOME/.streamlit"
[ -f "$HOME/.streamlit/credentials.toml" ] || printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
streamlit run dashboard/app.py --browser.gatherUsageStats false
