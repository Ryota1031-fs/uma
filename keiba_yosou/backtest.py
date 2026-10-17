"""過去データで的中率・回収率を確かめ、画面で使うモデルを保存する。

日付で前半を学習、後半を検証に分け、各レースで確率上位 N 点を100円ずつ買ったとして集計する。
単勝・複勝は、確率 × オッズ（期待値）が基準を超える馬だけを買う方法も試す。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import build
from .features import RACE_KEY, add_features
from .model import TICKET_TYPES, BlendModel, GBMModel, MarketModel, ticket_probs

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
# 画面で過去成績を計算するのに使う列（馬名などは入れず、番号と数値だけ）
HISTORY_COLS = ["race_id", "date", "num", "horse_id", "jockey_id", "trainer_id", "position", "status",
                "time", "last3f", "corner_last", "distance", "surface"]


def training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """出走した馬だけにし、着順のそろったレースを残す。"""
    f = add_features(df)
    f = f[f["running"]]
    ok = f.groupby(RACE_KEY)["position"].transform(lambda s: (s == 1).any())
    return f[ok].reset_index(drop=True)


def evaluate(df: pd.DataFrame, probs: pd.Series, payouts: dict, n: int) -> pd.DataFrame:
    stats = {t: {"races": 0, "hits": 0, "cost": 0, "return": 0} for t in TICKET_TYPES}
    for rid, g in df.assign(prob=probs.values).groupby(RACE_KEY):
        pay = payouts.get(rid, {})
        for t, probs_t in ticket_probs(dict(zip(g["num"], g["prob"]))).items():
            combos = sorted(probs_t, key=lambda c: -probs_t[c])[:n]
            s = stats[t]
            s["races"] += 1
            s["cost"] += 100 * len(combos)
            got = [pay.get(t, {}).get(c, 0) for c in combos]
            s["return"] += sum(got)
            s["hits"] += any(got)
    out = pd.DataFrame(stats).T
    out["的中率"] = (out["hits"] / out["races"]).round(3)
    out["回収率"] = (out["return"] / out["cost"]).round(3)
    return out


def evaluate_value(df: pd.DataFrame, probs: pd.Series, payouts: dict, threshold: float,
                   min_prob: float = 0.02) -> pd.DataFrame:
    """期待値（確率 × 最終オッズ）が threshold 以上の単勝・複勝だけ100円ずつ買う。複勝は低い方のオッズで見積もる。"""
    rows = []
    d = df.assign(prob=probs.values)
    for rid, g in d.groupby(RACE_KEY):
        tp = ticket_probs(dict(zip(g["num"], g["prob"])))
        pay = payouts.get(rid, {})
        for _, h in g.iterrows():
            num = str(h["num"])
            for t, odds in (("単勝", h["odds"]), ("複勝", h["place_odds_min"])):
                p = tp[t][num]
                if pd.notna(odds) and p >= min_prob and p * odds >= threshold:
                    rows.append({"ticket": t, "return": pay.get(t, {}).get(num, 0)})
    r = pd.DataFrame(rows, columns=["ticket", "return"])
    out = r.groupby("ticket").agg(bets=("return", "size"), hits=("return", lambda s: (s > 0).sum()),
                                  ret=("return", "sum"))
    out["的中率"] = (out["hits"] / out["bets"]).round(3)
    out["回収率"] = (out["ret"] / (100 * out["bets"])).round(3)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="オッズどおり／LightGBM の的中率・回収率を比べる")
    p.add_argument("--test-ratio", type=float, default=0.2)
    p.add_argument("--top", type=int, default=5, help="券種ごとに買う点数（単勝・複勝は上位1点）")
    p.add_argument("--no-save", action="store_true")
    a = p.parse_args()

    raw, payouts = build()
    if raw.empty:
        raise SystemExit("学習データがありません。先に download.py でデータを取得してください。")
    df = training_frame(raw)
    dates = sorted(df["date"].unique())
    cut = dates[int(len(dates) * (1 - a.test_ratio))]
    train, test = df[df["date"] < cut], df[df["date"] >= cut].reset_index(drop=True)
    print(f"学習 {train['date'].nunique()}日 / 検証 {test['date'].nunique()}日（{cut} 以降）、"
          f"検証レース数 {test[RACE_KEY].nunique()}")

    blend = BlendModel().fit(train)
    print(f"オッズ＋LightGBM の重み: オッズ {blend.a:.2f}、LightGBM {blend.b:.2f}")
    models = [MarketModel(), GBMModel(use_odds=False).fit(train), GBMModel(use_odds=True).fit(train), blend]
    summary = {}
    won = (test["position"] == 1).to_numpy()
    for m in models:
        probs = m.predict(test)
        ll = float(np.log(np.clip(probs.to_numpy()[won], 1e-9, 1)).mean())
        print(f"\n== {m.name} ==\n1着馬への当てはまり（0に近いほど良い）: {ll:.4f}")
        top1 = evaluate(test, probs, payouts, 1).loc[["単勝", "複勝"]]
        topn = evaluate(test, probs, payouts, a.top).drop(index=["単勝", "複勝"])
        res = pd.concat([top1, topn])
        print(res[["races", "的中率", "回収率"]])
        summary[m.name] = {"logloss": ll, "table": res[["的中率", "回収率"]].to_dict("index")}
        if not isinstance(m, MarketModel):
            for th in (1.0, 1.2, 1.5):
                v = evaluate_value(test, probs, payouts, th)
                print(f"期待値 {th} 以上だけ買う:\n{v[['bets', '的中率', '回収率']]}")
                summary[m.name][f"value_{th}"] = v[["bets", "的中率", "回収率"]].to_dict("index")
    imp = models[1].importance()
    print("\nLightGBM（オッズなし）で効いている項目（上位15）:")
    print((imp / imp.sum()).head(15).round(3))

    if a.no_save:
        return
    MODELS.mkdir(parents=True, exist_ok=True)
    # 画面で使うモデルは全期間で学び直して保存する
    GBMModel(use_odds=False).fit(df).save(MODELS / "gbm.txt")
    GBMModel(use_odds=True).fit(df).save(MODELS / "gbm_odds.txt")
    full = BlendModel().fit(df)
    full.gbm.save(MODELS / "gbm_blend.txt")
    (MODELS / "blend.json").write_text(json.dumps({"a": full.a, "b": full.b}))
    (MODELS / "backtest.json").write_text(json.dumps(
        {"cut": cut, "test_races": int(test[RACE_KEY].nunique()), "top": a.top, "models": summary},
        ensure_ascii=False, indent=1, default=float))
    raw[HISTORY_COLS].to_csv(MODELS / "history.csv.gz", index=False)


if __name__ == "__main__":
    main()
