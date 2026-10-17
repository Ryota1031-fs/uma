"""各馬の1着確率を出し、そこから券種ごとの確率を計算する。

- オッズどおり: 単勝オッズの逆数をレース内で合計1にしたもの（世の中の見立て）
- LightGBM: 過去成績などから1着かどうかを学習し、レース内で合計1になるよう正規化する。
  オッズを材料に入れる版と入れない版を作り、比べる
券種の確率は Harville 法（1着確率から順に条件付きで掛け合わせる）で出す。
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from .features import BASE_FEATURES, ODDS_FEATURES, RACE_KEY

TICKET_TYPES = ["単勝", "複勝", "ワイド", "馬連", "馬単", "3連複", "3連単"]


def normalize_in_race(df: pd.DataFrame, values) -> pd.Series:
    s = pd.Series(np.asarray(values, dtype=float), index=df.index)
    return s / s.groupby(df[RACE_KEY]).transform("sum")


class MarketModel:
    name = "オッズどおり"

    def fit(self, df: pd.DataFrame) -> "MarketModel":
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        p = df["odds_prob"].fillna(df["odds_prob"].min() if df["odds_prob"].notna().any() else 0.01)
        return normalize_in_race(df, p)


def _X(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return df[features].apply(pd.to_numeric, errors="coerce").astype(float)


class GBMModel:
    def __init__(self, use_odds: bool = False, features: list[str] | None = None):
        self.features = features or (BASE_FEATURES + (ODDS_FEATURES if use_odds else []))
        self.model = None

    @property
    def name(self) -> str:
        return "LightGBM（オッズあり）" if any(f in ODDS_FEATURES for f in self.features) else "LightGBM（オッズなし）"

    def fit(self, df: pd.DataFrame) -> "GBMModel":
        import lightgbm as lgb

        d = df[df["position"].notna()]
        y = (d["position"] == 1).astype(int)
        self.model = lgb.LGBMClassifier(
            n_estimators=500, learning_rate=0.03, num_leaves=31,
            min_child_samples=50, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.8, verbose=-1,
        )
        self.model.fit(_X(d, self.features), y)
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        return normalize_in_race(df, self.model.predict_proba(_X(df, self.features))[:, 1])

    def importance(self) -> pd.Series:
        b = self.model.booster_ if hasattr(self.model, "booster_") else self.model.booster
        return pd.Series(b.feature_importance("gain"), index=b.feature_name()).sort_values(ascending=False)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.booster_.save_model(str(path))

    @classmethod
    def load(cls, path: Path) -> "GBMModel":
        import lightgbm as lgb

        booster = lgb.Booster(model_file=str(path))
        m = cls(features=booster.feature_name())

        class _Wrap:
            def __init__(self, b):
                self.booster = b

            def predict_proba(self, X):
                p = self.booster.predict(X)
                return np.column_stack([1 - p, p])

        m.model = _Wrap(booster)
        return m


class BlendModel:
    """オッズ（世の中の見立て）と、オッズを使わない LightGBM の確率を掛け合わせる。

    p ∝ オッズの確率^a × LightGBM の確率^b。a と b は、学習に使っていない期間で一番当てはまる値を選ぶ。
    オッズが市場の情報を、LightGBM が過去成績の情報を持つので、両方を足し合わせる形になる。
    """
    name = "オッズ＋LightGBM"

    def __init__(self, gbm: "GBMModel | None" = None, a: float = 1.0, b: float = 0.3):
        self.gbm, self.a, self.b = gbm, a, b

    def _parts(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        g = np.clip(self.gbm.predict(df).to_numpy(), 1e-6, 1)
        o = df["odds_prob"].to_numpy(dtype=float)
        o = np.where(np.isnan(o), g, np.clip(o, 1e-6, 1))  # オッズがない馬は LightGBM だけで見る
        return np.log(o), np.log(g)

    def _combine(self, df: pd.DataFrame, lo: np.ndarray, lg: np.ndarray, a: float, b: float) -> pd.Series:
        z = pd.Series(a * lo + b * lg, index=df.index)
        z = z - z.groupby(df[RACE_KEY]).transform("max")
        return normalize_in_race(df, np.exp(z))

    def fit(self, df: pd.DataFrame, valid_ratio: float = 0.25) -> "BlendModel":
        d = df[df["position"].notna()]
        dates = sorted(d["date"].unique())
        cut = dates[int(len(dates) * (1 - valid_ratio))]
        tr, va = d[d["date"] < cut], d[d["date"] >= cut]
        self.gbm = GBMModel(use_odds=False).fit(tr)
        lo, lg = self._parts(va)
        won = (va["position"] == 1).to_numpy()
        best = (-np.inf, 1.0, 0.0)
        for a in np.linspace(0.6, 1.4, 9):
            for b in np.linspace(0, 1.0, 11):
                ll = np.log(np.clip(self._combine(va, lo, lg, a, b).to_numpy()[won], 1e-9, 1)).mean()
                if ll > best[0]:
                    best = (ll, float(a), float(b))
        _, self.a, self.b = best
        self.gbm = GBMModel(use_odds=False).fit(d)  # 重みが決まったら全期間で学び直す
        return self

    def predict(self, df: pd.DataFrame) -> pd.Series:
        lo, lg = self._parts(df)
        return self._combine(df, lo, lg, self.a, self.b)


def _key(nums) -> str:
    return "-".join(str(n) for n in nums)


def ticket_probs(win_prob: dict[int, float]) -> dict[str, dict[str, float]]:
    """馬番→1着確率 から、券種ごとの {組番: 確率} を返す。組番の書き方は公式の払戻と同じ。"""
    nums = sorted(win_prob)
    p = np.array([win_prob[n] for n in nums], dtype=float)
    p = p / p.sum()
    n = len(nums)
    # P(1着i, 2着j, 3着k) を n×n×n の表にする
    rest1 = np.clip(1 - p, 1e-9, None)
    p12 = p[:, None] * p[None, :] / rest1[:, None]
    np.fill_diagonal(p12, 0)
    rest2 = np.clip(1 - p[:, None] - p[None, :], 1e-9, None)
    p123 = p12[:, :, None] * p[None, None, :] / rest2[:, :, None]
    idx = np.arange(n)
    p123[idx, :, idx] = 0
    p123[:, idx, idx] = 0
    top3 = p123.sum(axis=(1, 2)) + p123.sum(axis=(0, 2)) + p123.sum(axis=(0, 1))
    out = {t: {} for t in TICKET_TYPES}
    for i in range(n):
        out["単勝"][str(nums[i])] = float(p[i])
        out["複勝"][str(nums[i])] = float(min(top3[i], 1.0))
    for i, j in combinations(range(n), 2):
        a, b = nums[i], nums[j]
        out["馬連"][_key((a, b))] = float(p12[i, j] + p12[j, i])
        out["馬単"][_key((a, b))] = float(p12[i, j])
        out["馬単"][_key((b, a))] = float(p12[j, i])
        # ワイド: 2頭とも3着以内
        w = sum(p123[x, y, :].sum() + p123[x, :, y].sum() + p123[:, x, y].sum() for x, y in ((i, j), (j, i)))
        out["ワイド"][_key((a, b))] = float(w)
    for i, j, k in combinations(range(n), 3):
        tri = [(i, j, k), (i, k, j), (j, i, k), (j, k, i), (k, i, j), (k, j, i)]
        out["3連複"][_key((nums[i], nums[j], nums[k]))] = float(sum(p123[x] for x in tri))
        for x in tri:
            out["3連単"][_key(nums[c] for c in x)] = float(p123[x])
    return out


def top_tickets(win_prob: dict[int, float], n: int = 5) -> dict[str, list[tuple[str, float]]]:
    return {t: sorted(probs.items(), key=lambda kv: -kv[1])[:n] for t, probs in ticket_probs(win_prob).items()}
