"""出馬表から各馬の確率を出す（画面から使う）。"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import HISTORY_COLS, MODELS
from .dataset import TABLE_DIR
from .features import add_features
from .model import GBMModel, MarketModel

MODEL_FILES = {"LightGBM（オッズあり）": "gbm_odds.txt", "LightGBM（オッズなし）": "gbm.txt"}


def available_models() -> list[str]:
    """使えるモデルを、過去データでの当てはまりが良い順に返す（先頭が画面の初期値）。"""
    names = [n for n, f in MODEL_FILES.items() if (MODELS / f).exists()] + ["オッズどおり"]
    try:
        scores = json.loads((MODELS / "backtest.json").read_text(encoding="utf-8"))["models"]
        names.sort(key=lambda n: -scores.get(n, {}).get("logloss", -99))
    except (OSError, ValueError, KeyError):
        pass
    return names


def load_model(name: str):
    if name == "オッズどおり":
        return MarketModel()
    return GBMModel.load(MODELS / MODEL_FILES[name])


def load_history() -> pd.DataFrame:
    """過去成績の表。配布した models/history.csv.gz と、このPCで取り込んだ分（あれば）を合わせる。"""
    dtype = {"race_id": str, "horse_id": str, "jockey_id": str, "trainer_id": str}
    parts = []
    if (MODELS / "history.csv.gz").exists():
        parts.append(pd.read_csv(MODELS / "history.csv.gz", dtype=dtype))
    for f in sorted(Path(TABLE_DIR).glob("*_horses.csv.gz")):
        races = pd.read_csv(f.with_name(f.name.replace("horses", "races")), dtype={"race_id": str, "venue": str})
        h = pd.read_csv(f, dtype=dtype).merge(races, on="race_id", how="left")
        parts.append(h.reindex(columns=HISTORY_COLS))
    if not parts:
        return pd.DataFrame(columns=HISTORY_COLS)
    h = pd.concat(parts).drop_duplicates(["race_id", "num"], keep="last")
    return h.reset_index(drop=True)


def race_frame(info: dict, rows: list[dict], history: pd.DataFrame) -> pd.DataFrame:
    """1レース分の出走馬に、過去成績から作った数値を付けて返す（取消・除外の馬は外す）。"""
    target = pd.DataFrame(rows).assign(**{k: v for k, v in info.items() if k != "race_id"})
    # 結果ページから作ったときに混ざる、そのレース自身の着順やタイムは消しておく（予想に使わない）
    actual = target[["num", "position", "time"]].copy() if "time" in target else None
    for col in ("position", "time", "last3f", "corner_last"):
        target[col] = np.nan
    hist = history[history["race_id"] != info["race_id"]]
    hist = hist[hist["date"].astype(str) < info["date"]]
    df = add_features(pd.concat([hist, target], ignore_index=True))
    out = df[df["race_id"] == info["race_id"]]
    out = out[out["running"]].copy()
    if actual is not None:
        out = out.drop(columns=["position", "time"]).merge(actual, on="num", how="left")
    if "odds" in out:
        o = out["odds"].where(out["odds"] > 0)
        out["odds_prob"] = (1 / o) / (1 / o).sum()
    return out.reset_index(drop=True)


def predict(model, frame: pd.DataFrame) -> pd.Series:
    return model.predict(frame)
