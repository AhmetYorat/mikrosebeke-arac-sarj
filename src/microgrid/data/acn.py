"""Caltech ACN-Data'dan gerçek şarj oturumlarını indirir (YM-1 erişim denemesi; asıl kullanıcı YM-2).

API token ister: https://ev.caltech.edu/register adresinden ücretsiz alınır.
Token koda veya repoya yazılmaz; ortam değişkeninden okunur:
    export ACN_API_TOKEN="..."
    python -m microgrid.data.acn
"""
import base64
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from microgrid.config import REPO_ROOT

ACN_URL = "https://ev.caltech.edu/api/v1/sessions"
RAW_DIR = REPO_ROOT / "data" / "raw"


def fetch_sessions(token, site="caltech", start=None, end=None, max_pages=4, timeout=60) -> list:
    """Oturumları sayfa sayfa çeker (sayfa başına 25 oturum).

    start/end: "Mon, 01 Apr 2019 00:00:00 GMT" biçiminde (RFC 1123, UTC).
    """
    # API, token'ı kullanıcı adı olarak bekler; şifre boş.
    auth = base64.b64encode(f"{token}:".encode()).decode()
    conditions = []
    if start:
        conditions.append(f'connectionTime>="{start}"')
    if end:
        conditions.append(f'connectionTime<="{end}"')
    url = f"{ACN_URL}/{site}"
    if conditions:
        url += "?" + urllib.parse.urlencode({"where": " and ".join(conditions)})

    sessions = []
    for _ in range(max_pages):
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            page = json.load(resp)
        sessions.extend(page["_items"])
        nxt = page.get("_links", {}).get("next")
        if not nxt:
            break
        url = urllib.parse.urljoin("https://ev.caltech.edu/api/v1/", nxt["href"])
    return sessions


def sessions_to_frame(sessions) -> pd.DataFrame:
    """Oturumları talep modeli için gereken sütunlara indirger.

    Zamanlar UTC gelir; her oturumun kendi saat dilimine (site yereli) çevrilir,
    böylece varış saati dağılımı yerel saate göre okunur.
    """
    rows = []
    for s in sessions:
        tz = s.get("timezone") or "UTC"
        arrival = pd.to_datetime(s["connectionTime"], utc=True).tz_convert(tz)
        departure = pd.to_datetime(s["disconnectTime"], utc=True).tz_convert(tz)
        user = (s.get("userInputs") or [{}])[0]
        rows.append(
            {
                "session_id": s["sessionID"],
                "arrival": arrival,
                "departure": departure,
                "arrival_hour": arrival.hour + arrival.minute / 60,
                "duration_h": (departure - arrival).total_seconds() / 3600,
                "kwh_delivered": s["kWhDelivered"],
                "kwh_requested": user.get("kWhRequested"),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    token = os.environ.get("ACN_API_TOKEN")
    if not token:
        raise SystemExit("ACN_API_TOKEN tanımlı değil. Token: https://ev.caltech.edu/register")
    sessions = fetch_sessions(token)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(RAW_DIR) / "acn_caltech_sample.json"
    out.write_text(json.dumps(sessions), encoding="utf-8")
    df = sessions_to_frame(sessions)
    print(f"Yazıldı: {out} ({len(df)} oturum)")
    print(df.describe())
