"""JRA公式のレース結果ページ・オッズページ・出馬表ページを表に変換する。"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .jra import VENUES

TICKETS = {"win": "単勝", "place": "複勝", "wakuren": "枠連", "wide": "ワイド",
           "umaren": "馬連", "umatan": "馬単", "trio": "3連複", "tierce": "3連単"}
BABA = {"良": 0, "稍重": 1, "重": 2, "不良": 3}


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _num(s: str) -> float | None:
    m = re.search(r"-?[\d.]+", s.replace(",", ""))
    return float(m.group()) if m else None


def _id(a, prefix: str) -> str:
    """リンクの cname から馬・騎手・調教師の番号を取り出す。"""
    if a is None:
        return ""
    s = (a.get("href") or "") + (a.get("onclick") or "")
    m = re.search(prefix + r"(\d+)/", s)
    return m.group(1) if m else ""


def race_info(soup: BeautifulSoup, rid: str) -> dict:
    """レースの条件（距離・芝ダ・馬場など）。結果ページと出馬表で共通の見出し部分を読む。"""
    head = soup.select_one(".race_header") or soup
    course = _text(head.select_one(".cell.course"))
    dist = _num(course.replace(",", "")) if course else None
    category = _text(head.select_one(".cell.category"))
    if "障害" in course or "障害" in category:
        surface = "障害"
    else:
        surface = "ダート" if "ダート" in course else "芝"
    baba = None
    for li in head.select(".baba li"):
        cap, txt = _text(li.select_one(".cap")), _text(li.select_one(".txt"))
        if cap in ("芝", "ダート") and txt in BABA:
            if baba is None or (surface == "ダート") == (cap == "ダート") or (surface == "障害" and cap == "芝"):
                baba = BABA[txt]
    weather = ""
    w = head.select_one(".baba .weather .txt")
    if w:
        weather = _text(w)
    cls = _text(head.select_one(".cell.class"))
    return {
        "race_id": rid,
        "date": f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}",
        "venue": rid[8:10],
        "venue_name": VENUES.get(rid[8:10], rid[8:10]),
        "race": int(rid[14:16]),
        "race_name": _text(head.select_one(".race_name")),
        "category": category,
        "class": cls,
        "weight_rule": _text(head.select_one(".cell.weight")),
        "surface": surface,
        "distance": dist,
        "turn": "右" if "右" in course else ("左" if "左" in course else ""),
        "baba": baba,
        "weather": weather,
        "grade": _grade(head),
    }


def _grade(head) -> str:
    img = head.select_one(".race_name .grade_icon img")
    return img.get("alt", "") if img else ""


def _href(a) -> str:
    """馬名のリンク（JRA公式の競走馬情報ページ）。"""
    h = a.get("href", "") if a is not None else ""
    return f"https://www.jra.go.jp{h}" if h.startswith("/JRADB/") else ""


def _sex_age(s: str) -> tuple[str, int | None]:
    m = re.match(r"(牡|牝|セ|せん)(\d+)", s)
    return (m.group(1)[0], int(m.group(2))) if m else ("", None)


def _body_weight(s: str) -> tuple[float | None, float | None]:
    m = re.match(r"(\d+)\s*\(?([+-]?\d+)?", s)
    if not m:
        return None, None
    return float(m.group(1)), (float(m.group(2)) if m.group(2) else None)


def _time_sec(s: str) -> float | None:
    m = re.match(r"(?:(\d+):)?(\d+\.\d)", s)
    if not m:
        return None
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def parse_result(html: str, rid: str) -> tuple[dict, list[dict], dict[str, dict[str, int]]]:
    """結果ページ → (レース条件, 各馬の行, 払戻 {券種: {組番: 100円あたりの払戻}})。"""
    soup = BeautifulSoup(html, "lxml")
    info = race_info(soup, rid)
    rows = []
    table = soup.select_one("#race_result table")
    for tr in table.select("tbody tr") if table else []:
        place = _text(tr.select_one("td.place"))
        num = _num(_text(tr.select_one("td.num")))
        if num is None:
            continue
        waku_img = tr.select_one("td.waku img")
        sex, age = _sex_age(_text(tr.select_one("td.age")))
        bw, bw_diff = _body_weight(_text(tr.select_one("td.h_weight")))
        corners = [_num(_text(li)) for li in tr.select("td.corner li")]
        horse_a = tr.select_one("td.horse a")
        rows.append({
            "race_id": rid,
            "position": int(place) if place.isdigit() else None,
            "status": "" if place.isdigit() else place,
            "waku": int(_num(waku_img.get("alt", ""))) if waku_img else None,
            "num": int(num),
            "horse": _text(horse_a),
            "horse_id": _id(horse_a, r"pw01dud\d\d"),
            "horse_url": _href(horse_a),
            "sex": sex,
            "age": age,
            "carried": _num(_text(tr.select_one("td.weight"))),
            "jockey": _text(tr.select_one("td.jockey")),
            "jockey_id": _id(tr.select_one("td.jockey a"), "pw04kmk00") or _text(tr.select_one("td.jockey")),
            "time": _time_sec(_text(tr.select_one("td.time"))),
            "last3f": _num(_text(tr.select_one("td.f_time"))),
            "corner_last": corners[-1] if corners else None,
            "body_weight": bw,
            "body_weight_diff": bw_diff,
            "trainer": _text(tr.select_one("td.trainer")),
            "trainer_id": _id(tr.select_one("td.trainer a"), "pw05cmk00") or _text(tr.select_one("td.trainer")),
            "popularity": _num(_text(tr.select_one("td.pop"))),
        })
    payouts: dict[str, dict[str, int]] = {}
    for key, name in TICKETS.items():
        li = soup.select_one(f".refund_area li.{key}")
        if not li:
            continue
        for line in li.select(".line"):
            combo = _text(line.select_one(".num"))
            yen = _num(_text(line.select_one(".yen")))
            if combo and yen:
                payouts.setdefault(name, {})[combo.replace(" ", "")] = int(yen)
    return info, rows, payouts


def parse_odds(html: str) -> dict[int, dict[str, float | None]]:
    """単勝・複勝オッズページ → {馬番: {"win": 単勝, "place_min": 複勝下限, "place_max": 複勝上限}}。"""
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for tr in soup.select("table tbody tr"):
        tan = tr.select_one("td.odds_tan")
        num = _num(_text(tr.select_one("td.num")))
        if tan is None or num is None:
            continue
        out[int(num)] = {
            "win": _num(_text(tan)),
            "place_min": _num(_text(tr.select_one("td.odds_fuku .min"))),
            "place_max": _num(_text(tr.select_one("td.odds_fuku .max"))),
        }
    return out


def parse_entries(html: str, rid: str) -> tuple[dict, list[dict]]:
    """出馬表ページ → (レース条件, 各馬の行)。オッズと馬体重は出ていれば入る。"""
    soup = BeautifulSoup(html, "lxml")
    info = race_info(soup, rid)
    rows = []
    for tr in soup.select("table tbody tr"):
        horse_td = tr.select_one("td.horse")
        if horse_td is None or horse_td.select_one(".name_line") is None:
            continue
        num = _num(_text(tr.select_one("td.num")))
        if num is None:
            continue
        waku_img = tr.select_one("td.waku img")
        horse_a = horse_td.select_one(".name a")
        sex, age = _sex_age(_text(tr.select_one("td.jockey p.age")))
        bw, bw_diff = _body_weight(_text(horse_td.select_one(".cell.weight")).replace("kg", ""))
        jockey_p = tr.select_one("td.jockey p.jockey")
        trainer_p = horse_td.select_one("p.trainer")
        status = next((s for s in ("取消", "除外", "中止") if s in _text(horse_td.select_one(".name_line"))), "")
        rows.append({
            "race_id": rid,
            "position": None,
            "status": status,
            "waku": int(_num(waku_img.get("alt", ""))) if waku_img else None,
            "num": int(num),
            "horse": _text(horse_a),
            "horse_id": _id(horse_a, r"pw01dud\d\d"),
            "horse_url": _href(horse_a),
            "sex": sex,
            "age": age,
            "carried": _num(_text(tr.select_one("td.jockey p.weight"))),
            "jockey": _text(jockey_p),
            "jockey_id": _id(jockey_p.select_one("a") if jockey_p else None, "pw04kmk00") or _text(jockey_p),
            "body_weight": bw,
            "body_weight_diff": bw_diff,
            "trainer": _text(trainer_p.select_one("a")) if trainer_p else "",
            "trainer_id": (_id(trainer_p.select_one("a"), "pw05cmk00") if trainer_p else "")
            or (_text(trainer_p.select_one("a")) if trainer_p else ""),
            "odds": _num(_text(horse_td.select_one(".odds .num"))),
            "popularity": _num(_text(horse_td.select_one(".odds .pop_rank"))),
        })
    return info, rows
