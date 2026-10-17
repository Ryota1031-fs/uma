"""予想を Discord のチャンネルに投稿する（ウェブフック）。

ウェブフックのURLを知っている人は誰でもそのチャンネルに投稿できるので、URLはこのPCの data/discord.json にだけ保存する
（data/ は GitHub に上げず、アプリの更新でも消えない）。
投稿するのはアプリが計算した予想だけ。出馬表などの公式のデータそのものは載せず、公式のページへのリンクを付ける。
"""
from __future__ import annotations

import json
import re

import requests

from .download import DATA_DIR

CONFIG = DATA_DIR.parent / "discord.json"
URL_PATTERN = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
OFFICIAL = "https://www.jra.go.jp/keiba/"


def load_url() -> str:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("webhook_url", "")
    except (OSError, ValueError):
        return ""


def save_url(url: str) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"webhook_url": url.strip()}), encoding="utf-8")


def valid_url(url: str) -> bool:
    return bool(URL_PATTERN.match(url.strip()))


def _combo(c: str) -> str:
    return "-".join(f"**{n}**" for n in c.split("-"))


def format_message(title: str, model: str, win_probs: dict[int, float], picks: dict[str, list[dict]],
                   values: list[dict]) -> str:
    """picks は {券種: [{combo, prob}]}、values は妙味のある買い目 [{ticket, combo, prob, odds, ev}]。"""
    top = sorted(win_probs.items(), key=lambda kv: -kv[1])[:6]
    lines = [
        f"🏇 **{title}** の予想（{model}）",
        "",
        "**1着確率（上位）**",
        "  ".join(f"{n}番 {p:.0%}" for n, p in top),
        "",
        "**おすすめの買い目**",
    ]
    for t, xs in picks.items():
        lines.append(f"{t}：" + "　".join(f"{_combo(x['combo'])} {x['prob']:.1%}" for x in xs))
    if values:
        lines += ["", "**妙味のある買い目**（確率 × オッズ = 期待値）"]
        for x in values:
            lines.append(f"{x['ticket']} {_combo(x['combo'])} {x['prob']:.1%} × {x['odds']:.1f}倍 = {x['ev']:.2f}")
    lines += ["", f"出馬表・オッズ: <{OFFICIAL}>",
              "※確率は過去の傾向から計算した目安です。馬券は無理のない範囲で。"]
    return "\n".join(lines)[:2000]  # Discord の1投稿は2000文字まで


def send(url: str, content: str) -> None:
    resp = requests.post(url, json={"content": content, "username": "競馬予想"}, timeout=15)
    resp.raise_for_status()
