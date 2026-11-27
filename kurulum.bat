@echo off
rem Mikro-sebeke projesi: kurulum + veri + dashboard (Windows). Cift tiklayinca calisir.
rem kurulum.command'in (macOS) Windows karsiligi. Mesajlar bilerek Turkce karaktersiz (cmd kod sayfasi sorunu olmasin).
setlocal
cd /d "%~dp0"
title Mikro-sebeke + EV sarj istasyonu - kurulum
echo == Proje klasoru: %CD%

rem 1) Python 3.10+ bul: once py baslaticisi, sonra PATH'teki python
set "PYEXE="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PYEXE (
    for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
  )
)
if not defined PYEXE (
  for /f "delims=" %%P in ('python -c "import sys; print(sys.executable if sys.version_info >= (3,10) else '')" 2^>nul') do set "PYEXE=%%P"
)

rem Python yoksa winget ile Python 3.12 kur (kullanici kapsaminda, yonetici gerekmez)
if not defined PYEXE (
  where winget >nul 2>&1
  if errorlevel 1 goto :python_yok
  echo == Python 3.10+ bulunamadi, winget ile Python 3.12 kuruluyor ^(birkac dakika surebilir^)...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PYEXE goto :python_yok
echo == Kullanilan Python: %PYEXE%

rem 2) Sanal ortam (.venv); eski/bozuk ortam varsa yeniden kurulur
set "VPY=.venv\Scripts\python.exe"
if exist "%VPY%" (
  "%VPY%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
  if errorlevel 1 rmdir /s /q .venv
)
if not exist "%VPY%" (
  echo == Sanal ortam ^(.venv^) olusturuluyor...
  "%PYEXE%" -m venv .venv
  if errorlevel 1 goto :hata
)
"%VPY%" -m pip install -q --upgrade pip
echo == Paketler kuruluyor ^(ilk seferde birkac dakika^)...
"%VPY%" -m pip install -q -r requirements.txt
if errorlevel 1 goto :hata

rem 3) Gercek veri (bir kez; varsa atlanir)
if not exist "data\processed\*.csv" (
  echo == Gercek veri indiriliyor ^(PVGIS^)...
  "%VPY%" -m microgrid.data
  if errorlevel 1 echo !! Veri hazirlanamadi; dashboard sahte girdiyle acilacak ^(ustte sari uyari^).
)

rem 4) Dashboard. Streamlit'in ilk acilistaki "Email:" sorusunu atla (bos e-posta kaydi)
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
  > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
  >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)
echo == Dashboard aciliyor: http://localhost:8501  ^(kapatmak icin bu pencerede Ctrl+C^)
"%VPY%" -m streamlit run dashboard\app.py --browser.gatherUsageStats false
pause
exit /b 0

:python_yok
echo !! Python 3.10 veya ustu bulunamadi ve otomatik kurulamadi.
echo    python.org'dan Python 3.12 Windows yukleyicisini kurun ^("Add python.exe to PATH" kutusunu isaretleyin^),
echo    sonra bu dosyaya tekrar cift tiklayin.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:hata
echo !! Kurulum basarisiz. Yukaridaki hata mesajini ekip arkadasina gonderin.
pause
exit /b 1
