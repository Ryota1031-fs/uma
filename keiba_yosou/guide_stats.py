"""見方ガイドに載せる数字を、取り込んだ過去データから集計して models/guide_stats.json に書く。"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .backtest import MODELS, training_frame
from .dataset import build


def _rate(df: pd.DataFrame, by, target: str) -> dict:
    return {str(k): round(float(v), 3) for k, v in df.groupby(by, observed=True)[target].mean().items()}


def main() -> None:
    raw, payouts = build()
    df = training_frame(raw)
    df["win"] = (df["position"] == 1).astype(float)
    df["top3"] = (df["position"] <= 3).astype(float)
    win_pay = {(rid, n): v for rid, p in payouts.items() for n, v in p.get("単勝", {}).items()}
    place_pay = {(rid, n): v for rid, p in payouts.items() for n, v in p.get("複勝", {}).items()}
    df["win_ret"] = [win_pay.get((r, str(n)), 0) for r, n in zip(df["race_id"], df["num"])]
    df["place_ret"] = [place_pay.get((r, str(n)), 0) for r, n in zip(df["race_id"], df["num"])]
    s: dict = {
        "races": int(df["race_id"].nunique()),
        "from": str(df["date"].min()), "to": str(df["date"].max()),
    }
    pop = df[df["popularity"].between(1, 18)].copy()
    pop["pop_band"] = pop["popularity"].clip(upper=10).astype(int)
    s["pop_win"] = _rate(pop, "pop_band", "win")
    s["pop_top3"] = _rate(pop, "pop_band", "top3")
    s["pop_win_roi"] = {k: round(v / 100, 3) for k, v in _rate(pop, "pop_band", "win_ret").items()}
    s["pop_place_roi"] = {k: round(v / 100, 3) for k, v in _rate(pop, "pop_band", "place_ret").items()}
    # 枠: 芝とダートで、内（1〜2枠）と外（7〜8枠）の3着内率
    flat = df[df["surface"].isin(["芝", "ダート"])]
    s["waku_top3"] = {surf: _rate(g, "waku", "top3") for surf, g in flat.groupby("surface")}
    # 前走の着順
    prev = df[df["h_last_pos"].notna()].copy()
    prev["prev_band"] = pd.cut(prev["h_last_pos"], [0, 1, 2, 3, 5, 9, 99],
                               labels=["1着", "2着", "3着", "4〜5着", "6〜9着", "10着以下"])
    s["prev_top3"] = _rate(prev, "prev_band", "top3")
    # 休み明け
    rest = df[df["h_days_since"].notna()].copy()
    rest["rest_band"] = pd.cut(rest["h_days_since"], [0, 20, 35, 63, 182, 9999],
                               labels=["中2週まで", "中3〜4週", "中5〜8週", "2〜6か月", "半年以上"])
    s["rest_top3"] = _rate(rest, "rest_band", "top3")
    # 馬体重の増減
    bw = df[df["body_weight_diff"].notna()].copy()
    bw["bw_band"] = pd.cut(bw["body_weight_diff"], [-99, -11, -3, 2, 10, 99],
                           labels=["-12kg以上減", "-10〜-4kg", "-2〜+2kg", "+4〜+10kg", "+12kg以上増"])
    s["bw_top3"] = _rate(bw, "bw_band", "top3")
    # 騎手の勝率（そのレースまでの成績）で5つに分ける
    df["j_band"] = pd.qcut(df["j_win_rate"].rank(method="first"), 5,
                           labels=["いちばん低い組", "低い組", "ふつう", "高い組", "いちばん高い組"])
    s["jockey_top3"] = _rate(df, "j_band", "top3")
    # 1番人気の1着率（頭数・クラス別）と、1番人気が負けたときの3連単
    fav = df[df["popularity"] == 1].copy()
    fav["field_band"] = pd.cut(fav["field_size"], [0, 10, 14, 18], labels=["10頭以下", "11〜14頭", "15頭以上"])
    s["fav_win_by_field"] = _rate(fav, "field_band", "win")
    s["fav_win_by_class"] = _rate(fav, "class", "win")
    tri = {rid: sum(p.get("3連単", {}).values()) for rid, p in payouts.items() if p.get("3連単")}
    fav_won = fav.set_index("race_id")["win"]
    t = pd.DataFrame({"pay": pd.Series(tri)}).join(fav_won.rename("fav_won"), how="inner")
    s["tri_median"] = int(t["pay"].median())
    s["tri_median_fav_won"] = int(t.loc[t["fav_won"] == 1, "pay"].median())
    s["tri_median_fav_lost"] = int(t.loc[t["fav_won"] == 0, "pay"].median())
    s["fav_win"] = round(float(fav["win"].mean()), 3)
    MODELS.mkdir(parents=True, exist_ok=True)
    (MODELS / "guide_stats.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(json.dumps(s, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
