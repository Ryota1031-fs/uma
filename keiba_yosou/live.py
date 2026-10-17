"""日付を指定して、その日のレース一覧・出馬表・結果を公式から取る。

- 今週の開催（出馬表が出ているレース）は、出馬表ページから
- 終わったレースは、過去レース結果のページから
取ったページは data/live/ に置き、同じものを何度も取りにいかない（オッズは毎回取り直す）。
"""
from __future__ import annotations

import gzip
import time
from datetime import date
from pathlib import Path

from . import jra
from .download import DATA_DIR, month_cnames
from .parse import parse_entries, parse_result

LIVE_DIR = DATA_DIR.parent / "live"


def _cached(name: str, path: str, cname: str, max_age: float | None) -> str:
    """max_age 秒より新しい控えがあればそれを使う。None なら一度取ったものをずっと使う。"""
    p = LIVE_DIR / name
    if p.exists() and (max_age is None or time.time() - p.stat().st_mtime < max_age):
        return gzip.decompress(p.read_bytes()).decode("utf-8")
    html = jra.fetch(path, cname)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(html.encode("utf-8")))
    return html


def entry_races(d: date) -> dict[str, str]:
    """{race_id: 出馬表の cname}。今週の開催で、出馬表が出ている日だけ。"""
    top = _cached("dli.html.gz", "/JRADB/accessD.html", "pw01dli00/F3", 600)
    out = {}
    for day in jra.links(top, "pw01drl"):
        if day.split("/")[0].endswith(f"{d:%Y%m%d}"):
            races = _cached(f"{d:%Y%m%d}/{day[9:11]}_drl.html.gz", "/JRADB/accessD.html", day, 600)
            for c in jra.links(races, "pw01dde"):
                out[jra.race_id(c)] = c
    return dict(sorted(out.items()))


def result_races(d: date) -> dict[str, str]:
    """{race_id: 結果ページの cname}。結果が出ている日だけ。"""
    ym = f"{d:%Y%m}"
    cname = month_cnames_cached().get(ym)
    if not cname:
        return {}
    today = d >= date.today()
    month = _cached(f"month_{ym}.html.gz", "/JRADB/accessS.html", cname, 600 if d.month == date.today().month else None)
    out = {}
    for day in jra.links(month, "pw01srl"):
        if day.split("/")[0].endswith(f"{d:%Y%m%d}"):
            races = _cached(f"{d:%Y%m%d}/{day[9:11]}_srl.html.gz", "/JRADB/accessS.html", day, 600 if today else None)
            for c in jra.links(races, "pw01sde"):
                out[jra.race_id(c)] = c
    return dict(sorted(out.items()))


_months: dict[str, str] = {}


def month_cnames_cached() -> dict[str, str]:
    global _months
    if not _months:
        _months = month_cnames()
    return _months


def entries(rid: str, cname: str, max_age: float = 300) -> tuple[dict, list[dict], str]:
    """(レース条件, 各馬, 単勝・複勝オッズページの cname)。オッズと馬体重は直前まで変わるので5分ごとに取り直す。"""
    html = _cached(f"{rid[:8]}/{rid}_entries.html.gz", "/JRADB/accessD.html", cname, max_age)
    info, rows = parse_entries(html, rid)
    odds = jra.links(html, "pw151ou")
    return info, rows, (odds[0] if odds else "")


def result(rid: str, cname: str) -> tuple[dict, list[dict], dict, str]:
    """(レース条件, 各馬の着順, 払戻, オッズページの cname)。"""
    html = _cached(f"{rid[:8]}/{rid}_result.html.gz", "/JRADB/accessS.html", cname, None)
    info, rows, pay = parse_result(html, rid)
    odds = jra.links(html, "pw151ou")
    return info, rows, pay, (odds[0] if odds else "")


def final_odds(rid: str, cname: str) -> str:
    return _cached(f"{rid[:8]}/{rid}_odds.html.gz", "/JRADB/accessO.html", cname, None)
