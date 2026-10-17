"""取り込んだ結果ページとオッズページを1つの表にまとめる。

一度読んだレースは data/table/ に月ごとの表として残し、次からは新しい月だけ読む。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .download import DATA_DIR, load
from .parse import parse_odds, parse_result

TABLE_DIR = DATA_DIR.parent / "table"


def _month(month_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    infos, rows, pays = [], [], {}
    for rp in sorted(month_dir.glob("*_result.html.gz")):
        rid = rp.name.split("_")[0]
        try:
            info, horses, payout = parse_result(load(rp), rid)
        except Exception as e:  # 読めないページは飛ばして続ける
            print(f"{rid}: 読めませんでした ({e})")
            continue
        op = rp.with_name(f"{rid}_odds.html.gz")
        odds = parse_odds(load(op)) if op.exists() else {}
        for h in horses:
            o = odds.get(h["num"], {})
            h["odds"] = o.get("win")
            h["place_odds_min"] = o.get("place_min")
            h["place_odds_max"] = o.get("place_max")
        infos.append(info)
        rows += horses
        pays[rid] = payout
    return pd.DataFrame(infos), pd.DataFrame(rows), pays


def build(refresh_latest: bool = True) -> tuple[pd.DataFrame, dict]:
    """(各馬の行にレース条件を付けた表, {race_id: 払戻}) を返す。"""
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    months = sorted(p for p in DATA_DIR.glob("[0-9]" * 6) if p.is_dir())
    races, horses, pays = [], [], {}
    for i, m in enumerate(months):
        rf, hf, pf = (TABLE_DIR / f"{m.name}_{k}" for k in ("races.csv.gz", "horses.csv.gz", "pay.json"))
        n_files = len(list(m.glob("*.html.gz")))
        stale = not rf.exists() or (refresh_latest and i >= len(months) - 2) or _count(pf) != n_files
        if stale:
            r, h, p = _month(m)
            r.to_csv(rf, index=False)
            h.to_csv(hf, index=False)
            pf.write_text(json.dumps({"files": n_files, "pay": p}, ensure_ascii=False))
        r = pd.read_csv(rf, dtype={"race_id": str, "venue": str})
        h = pd.read_csv(hf, dtype={"race_id": str, "horse_id": str, "jockey_id": str, "trainer_id": str})
        races.append(r)
        horses.append(h)
        pays.update(json.loads(pf.read_text())["pay"])
    if not races:
        return pd.DataFrame(), {}
    df = pd.concat(horses).merge(pd.concat(races), on="race_id", how="left")
    return df.sort_values(["date", "race_id", "num"]).reset_index(drop=True), pays


def _count(pf: Path) -> int:
    try:
        return json.loads(pf.read_text())["files"]
    except (OSError, ValueError, KeyError):
        return -1


if __name__ == "__main__":
    df, pays = build()
    print(f"{df['race_id'].nunique()}レース、{len(df)}頭")
