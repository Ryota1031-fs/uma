"""JRA公式サイト（JRADB）からページを取る。

JRADB のページは cname という合言葉を POST して開く。cname はページ内のリンク
（doAction('/JRADB/accessS.html', 'pw01...')）に書かれているので、それを順にたどる。
公式サイトへの負荷を避けるため、1ページごとに間隔を空ける。
"""
from __future__ import annotations

import re
import time

import requests

BASE = "https://www.jra.go.jp"
HEADERS = {"User-Agent": "keiba-yosou personal research"}

# 競馬場コード（JRA）
VENUES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}

INTERVAL = 1.0  # 1ページごとの待ち秒数
_session: requests.Session | None = None
_last = 0.0


def fetch(path: str, cname: str) -> str:
    """path は '/JRADB/accessS.html' など。前回の取得から INTERVAL 秒は空ける。"""
    global _session, _last
    if _session is None:
        _session = requests.Session()
        _session.headers.update(HEADERS)
    wait = _last + INTERVAL - time.time()
    if wait > 0:
        time.sleep(wait)
    for attempt in range(3):
        try:
            resp = _session.post(BASE + path, data={"cname": cname}, timeout=30)
            resp.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    _last = time.time()
    return resp.content.decode("cp932", errors="replace")


def links(html: str, prefix: str) -> list[str]:
    """ページ内の cname のうち prefix で始まるものを、出てきた順に重複なしで返す。"""
    seen = []
    for c in re.findall(r"(" + re.escape(prefix) + r"[0-9A-Za-z]+/[0-9A-F]{2})", html):
        if c not in seen:
            seen.append(c)
    return seen


def race_id(cname: str) -> str:
    """pw01sde1005202604021120261004/60 → 2026100405040211
    （日付8桁 + 場2 + 回2 + 日目2 + R2 の16桁）にする。"""
    m = re.match(r"pw\d+[a-z]+[A-Z\d]\d(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})", cname)
    if not m:
        raise ValueError(cname)
    venue, _year, kai, nichi, race, ymd = m.groups()
    return f"{ymd}{venue}{kai}{nichi}{race}"
