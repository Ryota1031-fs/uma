"""JRA公式の過去レース結果と、そのレースの単勝・複勝オッズを取って保存する。

月ごとの開催一覧 → 開催日ごとのレース一覧 → 各レースの結果ページ → オッズページ の順にたどる。
ページはそのまま（gzip で圧縮して）data/raw/ に置き、取得済みのレースは飛ばす。
"""
from __future__ import annotations

import argparse
import gzip
import re
from datetime import date
from pathlib import Path

from . import jra

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def raw_path(rid: str, kind: str, out_dir: Path = DATA_DIR) -> Path:
    """kind は "result" か "odds"。"""
    return out_dir / rid[:6] / f"{rid}_{kind}.html.gz"


def save(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(html.encode("utf-8")))


def load(path: Path) -> str:
    return gzip.decompress(path.read_bytes()).decode("utf-8")


def month_cnames() -> dict[str, str]:
    """{"YYYYMM": cname}。過去レース結果検索ページにある照合表から作る。"""
    html = jra.fetch("/JRADB/accessS.html", "pw01skl00999999/B3")
    table = dict(re.findall(r'objParam\["(\d{4})"\]="([0-9A-F]{2})"', html))
    current = re.search(r'var yearMonth = "(\d{6})"', html).group(1)
    out = {}
    for yymm, check in table.items():
        yy = int(yymm[:2])
        ym = f"{(2000 + yy) if yy < 80 else (1900 + yy)}{yymm[2:]}"
        out[ym] = f"pw01skl{'00' if ym >= current else '10'}{ym}/{check}"
    return out


def race_cnames_of_month(cname: str) -> list[str]:
    month = jra.fetch("/JRADB/accessS.html", cname)
    races = []
    for day in jra.links(month, "pw01srl"):
        if day[9:11] not in jra.VENUES:
            continue
        races += jra.links(jra.fetch("/JRADB/accessS.html", day), "pw01sde")
    return races


def download_race(cname: str, with_odds: bool = True) -> str:
    rid = jra.race_id(cname)
    rp = raw_path(rid, "result")
    if rp.exists():
        html = load(rp)
    else:
        html = jra.fetch("/JRADB/accessS.html", cname)
        if "race_result" not in html:
            print(f"{rid}: 結果ページではありません")
            return rid
        save(rp, html)
    op = raw_path(rid, "odds")
    if with_odds and not op.exists():
        odds = jra.links(html, "pw151ou")
        if odds:
            save(op, jra.fetch("/JRADB/accessO.html", odds[0]))
    return rid


def download_range(start: date, end: date, with_odds: bool = True, interval: float = 1.0) -> None:
    jra.INTERVAL = interval
    months = month_cnames()
    ym = f"{start:%Y%m}"
    while ym <= f"{end:%Y%m}":
        if ym in months:
            done_marker = DATA_DIR / ym / ".done"
            if not done_marker.exists():
                cnames = race_cnames_of_month(months[ym])
                n = 0
                for c in cnames:
                    rid = jra.race_id(c)
                    if not (f"{start:%Y%m%d}" <= rid[:8] <= f"{end:%Y%m%d}"):
                        continue
                    download_race(c, with_odds)
                    n += 1
                print(f"{ym}: {n}レース", flush=True)
                if f"{end:%Y%m%d}" >= _month_end(ym) and ym < f"{date.today():%Y%m}":
                    done_marker.parent.mkdir(parents=True, exist_ok=True)
                    done_marker.write_text(str(n))
        y, m = int(ym[:4]), int(ym[4:])
        ym = f"{y + (m == 12)}{(m % 12) + 1:02d}"


def _month_end(ym: str) -> str:
    return f"{ym}31"


def main() -> None:
    p = argparse.ArgumentParser(description="JRA公式の過去レース結果とオッズをダウンロード")
    p.add_argument("start", type=date.fromisoformat)
    p.add_argument("end", type=date.fromisoformat)
    p.add_argument("--no-odds", action="store_true", help="オッズページを取らない")
    p.add_argument("--interval", type=float, default=1.0, help="1ページごとの待ち秒数")
    a = p.parse_args()
    download_range(a.start, a.end, not a.no_odds, a.interval)


if __name__ == "__main__":
    main()
