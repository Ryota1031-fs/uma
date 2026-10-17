"""予想の画面。app.py から開く。"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from keiba_yosou import discord, live, ui
from keiba_yosou.backtest import evaluate
from keiba_yosou.jra import VENUES
from keiba_yosou.model import TICKET_TYPES, ticket_probs
from keiba_yosou.odds import fetch_odds
from keiba_yosou.parse import parse_odds
from keiba_yosou.predict import available_models, load_history, load_model, race_frame

ROOT = Path(__file__).resolve().parent.parent
# Webに載せた版（Streamlit Community Cloud は /mount/src に置かれる）。GitHub に上げると自動で新しくなる
ON_CLOUD = str(ROOT).startswith("/mount/src")


def webhook_url() -> str:
    """Web版は見る人みんなに設定欄が見えるので、URLは管理画面の Secrets にだけ置く。"""
    if not ON_CLOUD:
        return discord.load_url()
    try:
        return st.secrets.get("discord_webhook_url", "")
    except Exception:  # Secrets が未設定
        return ""


st.markdown(ui.CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🏇 設定")
    race_date = st.date_input("開催日", value=date.today())
    top_n = st.slider("券種ごとの表示点数", 1, 10, 5)
    st.markdown("**妙味（期待値）の目安**")
    ev_line = st.slider("期待値がこれ以上なら印を付ける", 1.0, 2.0, 1.2, 0.05,
                        help="期待値 = 当たる確率 × オッズ。1を超えると、確率のわりに配当が高い買い目です")
    min_prob = st.slider("ただし当たる確率がこれ以上のものだけ", 0.0, 0.10, 0.02, 0.005, format="%.3f",
                         help="確率がとても低い大穴は、予想の確率そのものがぶれやすいので外します")
    st.divider()
    if st.button("出馬表・結果を取り直す", width="stretch", help="馬体重やオッズ、当日の結果を公式から取り直します"):
        st.session_state["force_refresh"] = time.time()
    if not ON_CLOUD:  # Web版はURLが見る人に見えないよう、Secrets で設定する
        with st.expander("Discord連携"):
            saved_url = discord.load_url()
            st.caption("友人のDiscordのチャンネルに予想を投稿します。URLはこのPCの中にだけ保存されます。")
            new_url = st.text_input("ウェブフックのURL", value=saved_url, type="password")
            if st.button("保存", width="stretch"):
                if discord.valid_url(new_url):
                    discord.save_url(new_url)
                    st.success("保存しました。予想画面の「Discordに送る」で投稿できます。")
                else:
                    st.error("ウェブフックのURLの形ではありません。Discordで「ウェブフックURLをコピー」したものを貼ってください。")
    st.divider()
    if not ON_CLOUD and st.button("アプリを最新版に更新", type="primary", width="stretch"):
        from keiba_yosou.update import update

        try:
            files = update()
            if files:
                st.cache_resource.clear()
                st.cache_data.clear()
                st.success(f"{len(files)}個のファイルを更新しました。黒い画面を閉じて、もう一度 start で開き直してください。")
            else:
                st.info("すでに最新です。")
        except Exception as e:
            st.error(f"更新できませんでした: {e}")


@st.cache_resource
def cached_model(name: str):
    return load_model(name)


@st.cache_data(show_spinner=False)
def cached_history() -> pd.DataFrame:
    return load_history()


@st.cache_data(ttl=600, show_spinner=False)
def race_lists(d: date, _bust: float) -> tuple[dict, dict]:
    """(出馬表の出ているレース, 結果の出ているレース)。"""
    try:
        e = live.entry_races(d)
    except Exception:
        e = {}
    r = {}
    if d <= date.today():
        try:
            r = live.result_races(d)
        except Exception:
            r = {}
    return e, r


bust = st.session_state.get("force_refresh", 0.0)
with st.spinner("公式からレース一覧を取得しています…"):
    entry_map, result_map = race_lists(race_date, bust)
all_races = sorted(set(entry_map) | set(result_map))

if not all_races:
    st.markdown(ui.hero("競馬予想", f"{race_date.year}年{race_date.month}月{race_date.day}日"), unsafe_allow_html=True)
    st.info("この日のJRAのレースは見つかりませんでした。出馬表はたいてい開催の2日前（木曜か金曜）に出ます。"
            "開催は主に土曜・日曜です。")
    st.stop()

venues = sorted({r[8:10] for r in all_races})
c1, c2, c3 = st.columns([2, 2, 3])
venue = c1.selectbox("競馬場", venues, format_func=lambda v: VENUES.get(v, v))
races = [r for r in all_races if r[8:10] == venue]
rid = c2.selectbox("レース", races, format_func=lambda r: f"{int(r[14:16])}R", key=f"race_{race_date}_{venue}")
models = available_models()
model_name = c3.radio("予想に使うモデル", models, horizontal=True,
                      help="LightGBM は過去のレースから学んだ予想です。「オッズあり」は締切前のオッズも材料にします。"
                           "「オッズどおり」は世の中の人気をそのまま確率にしたものです")

# ---- 出走馬（出馬表があればそちら、なければ結果ページから） ----
age = 0 if bust and time.time() - bust < 5 else 300
try:
    with st.spinner("出馬表を取得しています…"):
        if rid in entry_map:
            info, rows, odds_cname = live.entries(rid, entry_map[rid], max_age=age)
            res_info, res_rows, payouts = None, None, {}
            if rid in result_map:
                res_info, res_rows, payouts, _ = live.result(rid, result_map[rid])
        else:
            info, rows, payouts, odds_cname = live.result(rid, result_map[rid])
            res_rows = rows
            # 結果ページにはオッズがないので、最終オッズのページから足す
            if odds_cname:
                final = parse_odds(live.final_odds(rid, odds_cname))
                for r in rows:
                    o = final.get(r["num"], {})
                    r["odds"] = o.get("win")
except Exception as e:
    st.error(f"公式から取得できませんでした: {e}")
    st.stop()

race_done = bool(payouts)
title = f"{info['venue_name']} {info['race']}R {info['race_name']}"
cond = f"{info['surface']}{info['distance']:.0f}m" if info.get("distance") else info["surface"]
st.markdown(ui.hero(title, f"{race_date.year}年{race_date.month}月{race_date.day}日・{cond}・{info['class']}・"
                           f"{model_name}で予想"), unsafe_allow_html=True)

frame = race_frame(info, rows, cached_history())
if frame.empty:
    st.info("出走馬の情報がまだ出ていません。")
    st.stop()
model = cached_model(model_name)
frame["prob"] = model.predict(frame).values
g = frame.sort_values("num")
waku = {int(n): int(w) for n, w in zip(g["num"], g["waku"]) if pd.notna(w)}

# ---- オッズ（当日の締切前だけ取りにいける。終わったレースは単勝・複勝の最終オッズ） ----
odds_store = st.session_state.setdefault("odds", {})
is_live = rid in entry_map and not race_done
b1, b2, _ = st.columns([1, 1, 2])
discord_slot = b2.empty()  # 「Discordに送る」は買い目を計算したあとで、ここに置く
if is_live and odds_cname and b1.button("オッズを取得", width="stretch",
                                         help="全券種の締切前のオッズを取ります（数ページ取るので少し時間がかかります）"):
    try:
        with st.spinner("オッズを取得しています…"):
            odds_store[rid] = (fetch_odds(odds_cname), time.strftime("%H:%M"))
    except Exception as e:
        st.warning(f"オッズを取得できませんでした: {e}")
race_odds, odds_time = odds_store.get(rid, ({}, None))
if not race_odds and not is_live and "odds" in g:
    race_odds = {"単勝": {str(n): o for n, o in zip(g["num"], g["odds"]) if pd.notna(o)}}

status = []
if g["body_weight"].notna().all():
    status.append(ui.pill("馬体重 発表済み", "ok"))
else:
    status.append(ui.pill("馬体重 発表前", "wait"))
if odds_time:
    status.append(ui.pill(f"全券種オッズ {odds_time} 時点", "info"))
elif is_live:
    status.append(ui.pill("単勝オッズのみ（出馬表の時点）", "wait"))
if race_done:
    status.append(ui.pill("結果確定", "info"))
st.markdown(" ".join(status), unsafe_allow_html=True)

st.markdown(ui.section("各馬の1着確率"), unsafe_allow_html=True)
st.markdown(ui.horses_table(g, "prob"), unsafe_allow_html=True)

hit_combos = {(t, c): v for t, xs in payouts.items() for c, v in xs.items()}
all_probs = ticket_probs(dict(zip(g["num"].astype(int), g["prob"])))


def pick_info(t: str, c: str, p: float) -> dict:
    o = race_odds.get(t, {}).get(c)
    ev = p * o if o else None
    return {"combo": c, "prob": p, "odds": o, "ev": ev, "hit": hit_combos.get((t, c)),
            "value": ev is not None and ev >= ev_line and p >= min_prob}


st.markdown(ui.section("おすすめの買い目（当たりやすい順）"), unsafe_allow_html=True)
cards = []
for t in TICKET_TYPES:
    top = sorted(all_probs[t].items(), key=lambda kv: -kv[1])[:top_n]
    cards.append(ui.ticket_card(t, [pick_info(t, c, p) for c, p in top], waku))
st.markdown(f'<div class="pick-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

st.markdown(ui.section("妙味のある買い目（確率のわりに配当が高い順）"), unsafe_allow_html=True)
vals = []
if race_odds:
    cands = [pick_info(t, c, p) | {"ticket": t} for t in race_odds for c, p in all_probs.get(t, {}).items()]
    vals = sorted([x for x in cands if x["value"]], key=lambda x: -x["ev"])[:10]
    if vals:
        vcards = [ui.ticket_card(t, [x for x in vals if x["ticket"] == t], waku)
                  for t in TICKET_TYPES if any(x["ticket"] == t for x in vals)]
        st.markdown(f'<div class="pick-grid">{"".join(vcards)}</div>', unsafe_allow_html=True)
    else:
        st.caption(f"期待値 {ev_line:.2f} 以上（確率 {min_prob:.1%} 以上）の買い目はありません。見送りも選択肢です。")
    st.caption("期待値 = 予想の確率 × オッズ。1を超えるほど、確率のわりに配当が高い買い目です。"
               + ("オッズは締切まで動くので、直前に取り直してください。" if is_live else "終わったレースは単勝の最終オッズで計算しています。"))
if is_live and not odds_time:
    st.caption("いまは出馬表に出ている単勝オッズだけで計算しています。「オッズを取得」を押すと、全券種で妙味のある買い目を探します。")

# ---- Discord ----
if webhook_url():
    if discord_slot.button("Discordに送る", width="stretch", help="このレースの1着確率とおすすめの買い目（オッズがあれば妙味の買い目も）を投稿します"):
        msg = discord.format_message(
            f"{race_date.month}/{race_date.day} {title}", model_name, dict(zip(g["num"].astype(int), g["prob"])),
            {t: [pick_info(t, c, p) for c, p in sorted(all_probs[t].items(), key=lambda kv: -kv[1])[:top_n]]
             for t in ("単勝", "馬連", "3連複")},
            vals,
        )
        try:
            discord.send(webhook_url(), msg)
            st.toast("Discordに投稿しました。", icon="✅")
        except Exception as e:
            st.error(f"Discordに投稿できませんでした: {e}")

# ---- 結果 ----
st.markdown(ui.section("実際の結果"), unsafe_allow_html=True)
if not race_done:
    st.caption("このレースの結果はまだ公式に出ていません。レースが終わると少しして出ます（「出馬表・結果を取り直す」で更新）。")
else:
    res = pd.DataFrame(res_rows).sort_values("position", na_position="last")
    st.markdown(ui.result_places(res, dict(zip(g["num"].astype(int), g["prob"])), waku), unsafe_allow_html=True)
    pay_cards = [ui.payout_card(t, payouts.get(t, {}), waku) for t in TICKET_TYPES if t in payouts]
    st.markdown(f'<div class="pick-grid" style="margin-top:12px">{"".join(pay_cards)}</div>', unsafe_allow_html=True)

# ---- この日の成績（終わったレースを、いまの設定どおりに100円ずつ買った場合） ----
done_ids = [r for r in result_map if r[:8] == f"{race_date:%Y%m%d}"]
if done_ids:
    st.markdown(ui.section(f"この日の成績（{model_name}・単勝と複勝は1点、ほかは上位{top_n}点を100円ずつ）"),
                unsafe_allow_html=True)
    if st.button(f"この日の終わった{len(done_ids)}レースで成績を計算", help="結果ページを順に取るので少し時間がかかります"):
        frames, pays = [], {}
        bar = st.progress(0.0)
        for i, r in enumerate(done_ids):
            try:
                inf, rws, pay, oc = live.result(r, result_map[r])
                if oc:  # 結果ページにはオッズがないので、最終オッズを足す
                    final = parse_odds(live.final_odds(r, oc))
                    for x in rws:
                        x["odds"] = final.get(x["num"], {}).get("win")
                frames.append(race_frame(inf, rws, cached_history()))
                pays[r] = pay
            except Exception:
                pass
            bar.progress((i + 1) / len(done_ids))
        bar.empty()
        if frames:
            day = pd.concat(frames, ignore_index=True)
            probs = model.predict(day)
            top1 = evaluate(day, probs, pays, 1).loc[["単勝", "複勝"]]
            topn = evaluate(day, probs, pays, top_n).drop(index=["単勝", "複勝"])
            summary = pd.concat([top1, topn])
            kcards = []
            for t in TICKET_TYPES:
                s = summary.loc[t]
                tone = "good" if s["回収率"] >= 1 else "bad"
                kcards.append(ui.kpi(f"{t}（{int(s['races'])}レース）", f"回収率 {s['回収率']:.0%}", tone)
                              + f'<div class="note" style="margin-top:6px">的中率 {s["的中率"]:.0%}・'
                                f'{int(s["cost"]):,}円 → {int(s["return"]):,}円</div>')
            st.markdown(f'<div class="pick-grid">{"".join(f"<div>{k}</div>" for k in kcards)}</div>',
                        unsafe_allow_html=True)

st.markdown('<div class="note" style="margin-top:24px">確率は出馬表・過去の成績・オッズから計算した目安です。'
            '馬券の購入は20歳になってから、自己責任で、無理のない範囲で楽しんでください。</div>', unsafe_allow_html=True)
