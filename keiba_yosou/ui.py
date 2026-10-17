"""画面の見た目（HTML と CSS）。Streamlit の標準部品では出せない、枠の色や確率のバーをここで描く。"""
from __future__ import annotations

import html

import pandas as pd

# JRAの枠の色（1白・2黒・3赤・4青・5黄・6緑・7橙・8桃）と、その上の文字色
WAKU_COLORS = {
    1: ("#ffffff", "#1a1a1a"), 2: ("#222222", "#ffffff"), 3: ("#e60012", "#ffffff"), 4: ("#1d6fd8", "#ffffff"),
    5: ("#ffd800", "#1a1a1a"), 6: ("#14a048", "#ffffff"), 7: ("#f39800", "#1a1a1a"), 8: ("#f19ec2", "#1a1a1a"),
}

CSS = """
<style>
:root {
  --ink: #14213d; --muted: #6b7280; --line: #e5e7eb; --card: #ffffff;
  --accent: #1b7a3d; --accent-soft: #e7f5ec; --good: #0f9d58; --good-soft: #e6f6ee; --warn: #b45309; --warn-soft: #fff4e5;
}
.block-container { padding-top: 1.6rem; max-width: 1200px; }
.hero {
  background: linear-gradient(120deg, #0d3b23 0%, #1b7a3d 55%, #59b36b 100%);
  color: #fff; border-radius: 18px; padding: 22px 26px; margin-bottom: 18px;
  box-shadow: 0 8px 24px rgba(13, 59, 35, .18);
}
.hero h1 { font-size: 1.7rem; margin: 0; font-weight: 800; letter-spacing: .02em; color: #fff; }
.hero p { margin: 6px 0 0; opacity: .85; font-size: .95rem; }
.pill { display: inline-block; border-radius: 999px; padding: 3px 12px; font-size: .8rem; font-weight: 600; margin-right: 6px; }
.pill.ok { background: var(--good-soft); color: var(--good); }
.pill.wait { background: var(--warn-soft); color: var(--warn); }
.pill.info { background: var(--accent-soft); color: var(--accent); }
.sec { font-size: 1.15rem; font-weight: 800; color: var(--ink); margin: 22px 0 10px; display: flex; align-items: center; gap: 8px; }
.sec::before { content: ""; width: 6px; height: 1.1em; border-radius: 3px; background: var(--accent); display: inline-block; }
.chip {
  display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 7px;
  font-weight: 800; font-size: .9rem; border: 1px solid rgba(0,0,0,.18); margin-right: 3px;
}
.chip.lg { width: 34px; height: 34px; font-size: 1.05rem; border-radius: 9px; }
.boats { width: 100%; border-collapse: separate !important; border-spacing: 0 6px; border: none !important; margin: 0; }
.boats tr, .boats th { border: none !important; background: transparent !important; }
[data-testid="stMarkdownContainer"] table.boats td, [data-testid="stMarkdownContainer"] table.boats th { border-left: none !important; border-right: none !important; }
[data-testid="stMarkdownContainer"] table.boats th { border-top: none !important; border-bottom: none !important; }
.boats th { text-align: left; font-size: .75rem; color: var(--muted); font-weight: 600; padding: 0 10px; }
.boats td { border-left: none !important; border-right: none !important; background: var(--card); padding: 10px; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); font-size: .9rem; color: var(--ink); }
.boats td:first-child { border-left: 1px solid var(--line); border-radius: 12px 0 0 12px; }
.boats td:last-child { border-right: 1px solid var(--line); border-radius: 0 12px 12px 0; }
.boats tr.top td { background: #f1faf3; }
.name { font-weight: 700; font-size: .98rem; }
a.name { color: var(--ink); text-decoration: none; border-bottom: 1px dashed var(--accent); }
a.name:hover { color: var(--accent); }
.sub { color: var(--muted); font-size: .75rem; }
.cls { display: inline-block; border-radius: 6px; padding: 1px 7px; font-size: .72rem; font-weight: 700; margin-left: 6px; background: #eef0f3; color: #4b5563; }
.cls.fav { background: #fde7e9; color: #c0182b; }
.pick-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }
.bar { position: relative; height: 10px; background: #eef2f7; border-radius: 999px; overflow: hidden; min-width: 120px; }
.bar > span { position: absolute; inset: 0 auto 0 0; background: linear-gradient(90deg, #59b36b, #1b7a3d); border-radius: 999px; }
.pct { font-weight: 800; font-size: 1rem; color: var(--ink); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px 14px 8px; height: 100%; box-shadow: 0 2px 8px rgba(20,33,61,.04); }
.card h4 { margin: 0 0 8px; font-size: .95rem; color: var(--ink); }
.combo { display: inline-flex; flex-wrap: nowrap; white-space: nowrap; }
.card .chip { width: 22px; height: 22px; font-size: .8rem; border-radius: 6px; margin-right: 2px; }
.pick { display: flex; align-items: center; justify-content: space-between; padding: 7px 4px; border-top: 1px dashed var(--line); gap: 6px; }
.pick:first-of-type { border-top: none; }
.pick .p { font-weight: 700; color: var(--ink); font-size: .9rem; }
.pick .o { color: var(--muted); font-size: .75rem; text-align: right; }
.pick.value { background: var(--good-soft); border-radius: 10px; }
.tag { border-radius: 6px; padding: 1px 7px; font-size: .72rem; font-weight: 700; }
.tag.hit { background: #fff3c4; color: #8a5a00; }
.tag.ev { background: var(--good); color: #fff; }
.result { display: flex; gap: 10px; flex-wrap: wrap; }
.place { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 10px 14px; min-width: 140px; }
.place .rank { font-size: .75rem; color: var(--muted); font-weight: 700; }
.pay { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }
.pay .t { font-size: .8rem; color: var(--muted); font-weight: 700; }
.pay .y { font-size: 1.25rem; font-weight: 800; color: var(--ink); }
.kpi { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; }
.kpi .t { font-size: .8rem; color: var(--muted); font-weight: 700; }
.kpi .v { font-size: 1.3rem; font-weight: 800; color: var(--ink); }
.kpi .v.good { color: var(--good); } .kpi .v.bad { color: #c0182b; }
.note { color: var(--muted); font-size: .8rem; }
</style>
"""


def chip(num: int, waku: int | None = None, large: bool = False) -> str:
    bg, fg = WAKU_COLORS.get(int(waku), ("#eef0f3", "#14213d")) if waku else ("#eef0f3", "#14213d")
    return f'<span class="chip{" lg" if large else ""}" style="background:{bg};color:{fg}">{int(num)}</span>'


def combo(text: str, waku: dict[int, int]) -> str:
    return '<span class="combo">' + "".join(chip(int(n), waku.get(int(n))) for n in text.split("-")) + "</span>"


def hero(title: str, subtitle: str) -> str:
    return f'<div class="hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>'


def section(title: str) -> str:
    return f'<div class="sec">{html.escape(title)}</div>'


def pill(text: str, kind: str = "info") -> str:
    return f'<span class="pill {kind}">{html.escape(text)}</span>'


def _fmt(v, f: str, dash: str = "－") -> str:
    return format(v, f) if pd.notna(v) else dash


def _horse_name(r) -> str:
    name = html.escape(str(r["horse"]))
    url = r.get("horse_url")
    if isinstance(url, str) and url:
        return (f'<a class="name" href="{html.escape(url)}" target="_blank" rel="noopener" '
                f'title="JRA公式の競走馬情報（過去の成績）を開く">{name} ↗</a>')
    return f'<span class="name">{name}</span>'


def horses_table(g: pd.DataFrame, prob_col: str) -> str:
    best = g[prob_col].idxmax()
    rows = []
    for i, r in g.iterrows():
        p = float(r[prob_col])
        odds = f"{r['odds']:.1f}倍" if pd.notna(r.get("odds")) else "－"
        pop = f"{int(r['popularity'])}番人気" if pd.notna(r.get("popularity")) else ""
        fav = " fav" if pd.notna(r.get("popularity")) and r["popularity"] <= 3 else ""
        starts = int(r["h_starts"]) if pd.notna(r.get("h_starts")) else 0
        form = (f"{starts}戦・3着内 {r['h_top3_rate']:.0%}" if starts else "このデータでは初出走")
        last = (f"前走 {r['h_last_pos']:.0f}着/{r['h_last_field']:.0f}頭・{int(r['h_days_since'])}日ぶり"
                if pd.notna(r.get("h_last_pos")) and pd.notna(r.get("h_days_since")) else "")
        bw = (f"{r['body_weight']:.0f}kg（{r['body_weight_diff']:+.0f}）" if pd.notna(r.get("body_weight_diff"))
              else (f"{r['body_weight']:.0f}kg" if pd.notna(r.get("body_weight")) else "馬体重 発表前"))
        rows.append(
            f'<tr class="{"top" if i == best else ""}">'
            f'<td>{chip(r["num"], r.get("waku"), True)}</td>'
            f'<td>{_horse_name(r)}<span class="cls{fav}">{odds}</span>'
            f'<div class="sub">{html.escape(str(r["sex"]))}{_fmt(r.get("age"), ".0f")}・{_fmt(r.get("carried"), ".1f")}kg・{bw}</div></td>'
            f'<td>{html.escape(str(r["jockey"]))}<div class="sub">勝率 {r["j_win_rate"]:.0%}・{pop}</div></td>'
            f'<td>{form}<div class="sub">{last}</div></td>'
            f'<td style="width:30%"><div style="display:flex;align-items:center;gap:10px">'
            f'<div class="bar" style="flex:1"><span style="width:{min(p * 100 * 2, 100):.1f}%"></span></div>'
            f'<span class="pct">{p:.1%}</span></div></td></tr>'
        )
    head = "<tr><th>馬番</th><th>馬名・単勝オッズ</th><th>騎手</th><th>このデータでの成績</th><th>1着確率</th></tr>"
    return f'<table class="boats">{head}{"".join(rows)}</table>'


def ticket_card(ticket: str, picks: list[dict], waku: dict[int, int]) -> str:
    items = []
    for x in picks:
        tags = []
        if x.get("hit"):
            tags.append(f'<span class="tag hit">的中 {x["hit"]:,}円</span>')
        if x.get("value"):
            tags.append('<span class="tag ev">妙味</span>')
        odds = f'{x["odds"]:.1f}倍・期待値 {x["ev"]:.2f}' if x.get("odds") else ""
        items.append(
            f'<div class="pick{" value" if x.get("value") else ""}"><div>{combo(x["combo"], waku)}</div>'
            f'<div style="text-align:right"><div class="p">{x["prob"]:.1%} {"".join(tags)}</div><div class="o">{odds}</div></div></div>'
        )
    return f'<div class="card"><h4>{html.escape(ticket)}</h4>{"".join(items)}</div>'


def result_places(order: pd.DataFrame, probs: dict, waku: dict[int, int]) -> str:
    cells = []
    for _, r in order.head(3).iterrows():
        rank = f'{int(r["position"])}着' if pd.notna(r["position"]) else str(r["status"])
        cells.append(
            f'<div class="place"><div class="rank">{rank}</div>'
            f'<div style="display:flex;align-items:center;gap:8px;margin-top:4px">{chip(r["num"], waku.get(int(r["num"])), True)}'
            f'<div><div class="name">{html.escape(str(r["horse"]))}</div>'
            f'<div class="sub">予想の1着確率 {probs.get(int(r["num"]), 0):.1%}・{int(r["popularity"]) if pd.notna(r["popularity"]) else "－"}番人気</div></div></div></div>'
        )
    return f'<div class="result">{"".join(cells)}</div>'


def payout_card(ticket: str, pays: dict[str, int], waku: dict[int, int]) -> str:
    lines = "".join(f'<div style="margin:4px 0;display:flex;justify-content:space-between;gap:6px">{combo(c, waku)}'
                    f'<span class="y" style="font-size:1rem">{v:,}円</span></div>' for c, v in pays.items()) or "なし"
    return f'<div class="pay"><div class="t">{ticket}</div>{lines}<div class="sub">100円あたりの払戻</div></div>'


def kpi(title: str, value: str, tone: str = "") -> str:
    return f'<div class="kpi"><div class="t">{html.escape(title)}</div><div class="v {tone}">{value}</div></div>'


# 見方ガイドのページ用
GUIDE_CSS = """
<style>
.gcard { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px; margin-bottom: 14px;
  box-shadow: 0 2px 8px rgba(20,33,61,.04); color: var(--ink); }
.gcard h3 { font-size: 1rem; margin: 0 0 10px; color: var(--ink); }
.gcard p, .gcard li { font-size: .9rem; line-height: 1.7; }
.gcard ul, .gcard ol { padding-left: 1.2em; margin: 0; }
.steps li { margin-bottom: 4px; }
.gbar { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.gbar .gl { width: 110px; font-size: .85rem; font-weight: 700; color: var(--ink); }
.gbar .bar { flex: 1; height: 12px; }
.gbar .gv { width: 48px; text-align: right; font-weight: 800; font-size: .9rem; color: var(--ink); }
</style>
"""
