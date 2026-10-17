"""締切前のオッズを公式のオッズページから取る（単勝・複勝・ワイド・馬連・馬単・3連複・3連単）。

単勝・複勝のページに、ほかの券種のページへのリンクがあるので、それをたどる。
複勝とワイドは幅があるので、期待値を低めに見積もれるよう下限を使う。
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from . import jra
from .parse import _num, _text, parse_odds

PAGES = {"pw154ou": "馬連", "pw155ou": "ワイド", "pw156ou": "馬単", "pw157ou": "3連複", "pw158ou": "3連単"}


def _key(nums, ordered: bool) -> str:
    nums = [int(n) for n in nums]
    return "-".join(str(n) for n in (nums if ordered else sorted(nums)))


def parse_combo_odds(html: str, ticket: str) -> dict[str, float]:
    soup = BeautifulSoup(html, "lxml")
    out = {}
    cls = {"馬連": "umaren", "ワイド": "wide", "馬単": "umatan", "3連複": "fuku3", "3連単": "tan3"}[ticket]
    for tb in soup.select(f"table.{cls}"):
        if ticket == "3連単":
            li = tb.find_parent("li")
            head = [_text(x) for x in li.select(".p_line .num")] if li else []
        else:
            head = re.findall(r"\d+", _text(tb.select_one("caption")))
        if not head:
            continue
        for tr in tb.select("tbody tr"):
            last = _num(_text(tr.select_one("th")))
            td = tr.select_one("td")
            val = _num(_text(td.select_one(".min") or td)) if td else None
            if last is None or val is None:
                continue
            out[_key(head + [int(last)], ticket in ("馬単", "3連単"))] = val
    return out


def fetch_odds(win_cname: str, tickets=("単勝", "複勝", "ワイド", "馬連", "馬単", "3連複", "3連単")) -> dict[str, dict[str, float]]:
    """{券種: {組番: オッズ}} を返す。win_cname は出馬表ページにある単勝・複勝オッズのリンク。"""
    html = jra.fetch("/JRADB/accessO.html", win_cname)
    out: dict[str, dict[str, float]] = {"単勝": {}, "複勝": {}}
    for num, o in parse_odds(html).items():
        if o["win"]:
            out["単勝"][str(num)] = o["win"]
        if o["place_min"]:
            out["複勝"][str(num)] = o["place_min"]
    rid_part = win_cname[len("pw151ou"):].split("/")[0]
    for prefix, ticket in PAGES.items():
        if ticket not in tickets:
            continue
        link = next((c for c in jra.links(html, prefix) if rid_part in c), None)
        if link:
            out[ticket] = parse_combo_odds(jra.fetch("/JRADB/accessO.html", link), ticket)
    return out
