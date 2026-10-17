"""予想に使う数値（特徴量）を作る。

馬・騎手・調教師の成績は、そのレースより前の日のレースだけから計算する（未来の結果を混ぜない）。
出馬表（これから走るレース）も、過去の結果の表とつなげて同じ関数に通せば同じ数値になる。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RACE_KEY = "race_id"
CLASS_RANK = {"新馬": 0, "未勝利": 1, "1勝クラス": 2, "2勝クラス": 3, "3勝クラス": 4, "オープン": 5}
SURFACE = {"芝": 0, "ダート": 1, "障害": 2}
SEX = {"牡": 0, "牝": 1, "せ": 2}

# オッズ（人気）を使わない数値。モデルの比較に使う
BASE_FEATURES = [
    "venue_code", "surface_code", "distance", "baba", "class_rank", "field_size", "race",
    "waku", "num_ratio", "sex_code", "age", "carried", "carried_diff",
    "body_weight", "body_weight_diff",
    "h_starts", "h_win_rate", "h_top3_rate", "h_last_pos_ratio", "h_avg_pos_ratio3",
    "h_avg_margin3", "h_best_margin3", "h_avg_last3f_rank3", "h_avg_corner_ratio3", "h_days_since",
    "h_dist_diff", "h_surface_top3", "h_dist_top3",
    "j_win_rate", "j_top3_rate", "j_starts", "t_win_rate", "t_top3_rate",
    "h_avg_pos_ratio3_rank", "h_avg_margin3_rank", "j_win_rate_rank",
]
# 締切前のオッズ。学習には最終オッズを使う
ODDS_FEATURES = ["odds_log", "odds_prob", "popularity"]


def _prior_rate(df: pd.DataFrame, key: str, prefix: str, smooth: float = 20.0) -> pd.DataFrame:
    """key（騎手・調教師）ごとに、その日より前の勝率・3着内率を出す。少ない人は全体の平均に寄せる。"""
    k = pd.factorize(df[key].fillna("").astype(str))[0]  # 番号にしてつなぎやすくする
    d = pd.DataFrame({"k": k, "date": df["date"].to_numpy(), "position": df["position"].to_numpy()}, index=df.index)
    done = d[d["position"].notna()]
    daily = (done.assign(win=done["position"] == 1, top3=done["position"] <= 3, n=1)
             .groupby(["k", "date"])[["win", "top3", "n"]].sum().sort_index())
    cum = daily.groupby(level=0).cumsum().reset_index()  # その日までの累計
    cum["dt"] = pd.to_datetime(cum["date"])
    left = d[["k"]].assign(dt=pd.to_datetime(d["date"])).reset_index().sort_values("dt")
    # その日より前で一番近い日の累計を付ける（出馬表の日にも付く）
    out = pd.merge_asof(left, cum.drop(columns="date").sort_values("dt"), on="dt", by="k",
                        allow_exact_matches=False).set_index("index").reindex(df.index)
    base_win, base_top3 = 0.07, 0.21
    n = out["n"].fillna(0)
    return pd.DataFrame({
        f"{prefix}_starts": n,
        f"{prefix}_win_rate": (out["win"].fillna(0) + smooth * base_win) / (n + smooth),
        f"{prefix}_top3_rate": (out["top3"].fillna(0) + smooth * base_top3) / (n + smooth),
    }, index=df.index)


def _prior_mean(x: pd.Series, keys) -> pd.Series:
    """keys ごとに、その行より前の x の平均（欠けている値は数えない）。"""
    v, ok = x.fillna(0), x.notna().astype(float)
    total = v.groupby(keys).cumsum() - v
    n = ok.groupby(keys).cumsum() - ok
    return total / n.where(n > 0)


def _prior_rolling(x: pd.Series, keys: pd.Series, window: int, how: str) -> pd.Series:
    """keys ごとに、直前 window 走の平均か最小。"""
    prev = x.groupby(keys).shift(1)
    r = prev.groupby(keys).rolling(window, min_periods=1)
    return (r.mean() if how == "mean" else r.min()).reset_index(level=0, drop=True)


def _horse_history(df: pd.DataFrame) -> pd.DataFrame:
    """馬ごとに、前走までの成績をまとめる。"""
    d = df[["horse_id", "date", "position", "field_size", "margin", "last3f_rank",
            "corner_ratio", "distance", "surface"]].copy()
    d["date_dt"] = pd.to_datetime(d["date"])
    d = d.sort_values(["date_dt"], kind="stable")
    horse = pd.Series(pd.factorize(d["horse_id"].astype(str))[0], index=d.index)
    d["pos_ratio"] = d["position"] / d["field_size"]
    d["win"] = (d["position"] == 1).astype(float).where(d["position"].notna())
    d["top3"] = (d["position"] <= 3).astype(float).where(d["position"].notna())
    out = pd.DataFrame(index=d.index)
    ok = d["win"].notna().astype(float)
    out["h_starts"] = ok.groupby(horse).cumsum() - ok
    out["h_win_rate"] = _prior_mean(d["win"], horse)
    out["h_top3_rate"] = _prior_mean(d["top3"], horse)
    out["h_last_pos_ratio"] = d["pos_ratio"].groupby(horse).shift(1)
    out["h_last_pos"] = d["position"].groupby(horse).shift(1)  # 画面に出す用
    out["h_last_field"] = d["field_size"].groupby(horse).shift(1)
    for col, name in [("pos_ratio", "h_avg_pos_ratio3"), ("margin", "h_avg_margin3"),
                      ("last3f_rank", "h_avg_last3f_rank3"), ("corner_ratio", "h_avg_corner_ratio3")]:
        out[name] = _prior_rolling(d[col], horse, 3, "mean")
    out["h_best_margin3"] = _prior_rolling(d["margin"], horse, 3, "min")
    out["h_days_since"] = (d["date_dt"] - d["date_dt"].groupby(horse).shift(1)).dt.days
    out["h_dist_diff"] = d["distance"] - d["distance"].groupby(horse).shift(1)
    # 同じ芝ダ・近い距離（400m刻み）での3着内率
    surf = pd.Series(pd.factorize(d["horse_id"].astype(str) + "_" + d["surface"].astype(str))[0], index=d.index)
    out["h_surface_top3"] = _prior_mean(d["top3"], surf)
    band = pd.Series(pd.factorize(d["horse_id"].astype(str) + "_" + (d["distance"] / 400).round().astype(str))[0],
                     index=d.index)
    out["h_dist_top3"] = _prior_mean(d["top3"], band)
    return out.reindex(df.index)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """過去の結果と出馬表をつなげた表に、特徴量の列を足して返す。"""
    df = df.copy()
    df["date"] = df["date"].astype(str)
    run = df["status"].fillna("").astype(str).isin(["", "nan"])
    # 取消・除外の馬は頭数に数えない
    df["field_size"] = df["num"].where(run).groupby(df[RACE_KEY]).transform("count")
    df["venue_code"] = pd.to_numeric(df["venue"], errors="coerce")
    df["surface_code"] = df["surface"].map(SURFACE)
    df["class_rank"] = df["class"].map(CLASS_RANK)
    df["sex_code"] = df["sex"].map(SEX)
    df["num_ratio"] = df["num"] / df["field_size"]
    df["carried_diff"] = df["carried"] - df.groupby(RACE_KEY)["carried"].transform("mean")
    # 勝ち馬とのタイム差（秒）、上がり3Fの順位、最後のコーナーの位置（前にいるほど小さい）
    win_time = df["time"].where(df["position"] == 1).groupby(df[RACE_KEY]).transform("max")
    df["margin"] = (df["time"] - win_time).clip(upper=5)
    df["last3f_rank"] = df.groupby(RACE_KEY)["last3f"].rank(method="min") / df["field_size"]
    df["corner_ratio"] = df["corner_last"] / df["field_size"]
    df = df.join(_horse_history(df))
    df = df.join(_prior_rate(df, "jockey_id", "j"))
    df = df.join(_prior_rate(df, "trainer_id", "t"))
    g = df.groupby(RACE_KEY)
    df["h_avg_pos_ratio3_rank"] = g["h_avg_pos_ratio3"].rank(method="min") / df["field_size"]
    df["h_avg_margin3_rank"] = g["h_avg_margin3"].rank(method="min") / df["field_size"]
    df["j_win_rate_rank"] = g["j_win_rate"].rank(ascending=False, method="min") / df["field_size"]
    odds = df["odds"].where(df["odds"] > 0)
    df["odds_log"] = np.log(odds)
    df["odds_prob"] = (1 / odds) / (1 / odds).groupby(df[RACE_KEY]).transform("sum")
    df["running"] = run
    return df
