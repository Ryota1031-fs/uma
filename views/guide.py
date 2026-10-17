"""予想画面の見方と、自分で予想するときの手がかり。

数字は models/guide_stats.json（keiba_yosou.guide_stats で過去データから集計）から読む。
"""
import json

import streamlit as st

from keiba_yosou import ui
from keiba_yosou.backtest import MODELS

st.markdown(ui.CSS, unsafe_allow_html=True)
st.markdown(ui.GUIDE_CSS, unsafe_allow_html=True)


def bars(rows, scale: float = 1.0, fmt: str = "{:.0%}") -> str:
    """ラベルと割合の横棒。scale は棒の長さの最大（1.0 なら 100% で端まで）。"""
    out = []
    for label, v in rows:
        out.append(
            f'<div class="gbar"><div class="gl">{label}</div>'
            f'<div class="bar"><span style="width:{min(v / scale, 1) * 100:.1f}%"></span></div>'
            f'<div class="gv">{fmt.format(v)}</div></div>'
        )
    return "".join(out)


def box(title: str, body: str) -> None:
    st.markdown(f'<div class="gcard"><h3>{title}</h3>{body}</div>', unsafe_allow_html=True)


st.markdown(ui.hero("見方ガイド", "予想画面の読み方と、自分で予想するときに見るポイント"), unsafe_allow_html=True)

try:
    s = json.loads((MODELS / "guide_stats.json").read_text(encoding="utf-8"))
except (OSError, ValueError):
    s = None

if s:
    st.markdown(
        f'<div class="note">このページの数字は、JRAの {s["from"]}〜{s["to"]} のレース結果（{s["races"]:,}レース）を集計したものです。'
        "傾向であって、必ずそうなるわけではありません。</div>", unsafe_allow_html=True)

st.markdown(ui.section("まず見る順番"), unsafe_allow_html=True)
box("迷ったらこの5つ", """
<ol class="steps">
<li><b>人気（単勝オッズ）</b>：世の中の見立て。1番人気が勝つのは3回に1回ほど。</li>
<li><b>前走の着順と間隔</b>：前走で上位なら好調の目安。久しぶりのレースは割り引く。</li>
<li><b>騎手</b>：勝率の高い騎手が乗るのは、陣営が勝負をかけているサインでもある。</li>
<li><b>馬体重</b>：締切の1時間ほど前に出る。大きく増減した馬は注意。</li>
<li><b>オッズとの比較</b>：確率のわりに配当が高い買い目（妙味）があるか。なければ見送りも手。</li>
</ol>""")

st.markdown(ui.section("画面の見方"), unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    box("各馬の1着確率", """
<p>その馬が1着になる見込みです。全頭を足すと100%になります。</p>
<ul>
<li><b>単勝オッズ</b>：100円が何倍になるか。赤い印は3番人気まで。</li>
<li><b>性齢・斤量</b>：牡・牝・せん馬と年齢、背負う重さ（kg）。軽いほど有利。</li>
<li><b>馬体重</b>：（ ）は前走からの増減。当日に発表されます。</li>
<li><b>騎手の勝率</b>：このアプリが持つ過去データでの1着率。</li>
<li><b>このデータでの成績</b>：過去データの中での出走数と3着以内の割合、前走の着順と間隔。</li>
</ul>""")
with c2:
    box("買い目と期待値", """
<p><b>おすすめの買い目</b>は、1着確率から計算した「当たりやすい順」です。</p>
<ul>
<li><b>確率</b>：その組み合わせが当たる見込み。</li>
<li><b>倍率</b>：オッズ。100円が何倍になるか。</li>
<li><b>期待値</b> = 確率 × 倍率。1なら損得なし、1より大きいほど確率のわりに配当が高い。</li>
<li><b>妙味</b>の印：期待値が設定以上（初期値1.2）の買い目。</li>
<li><b>的中</b>の印：結果が出たあと、当たった組み合わせ。</li>
</ul>
<p class="note">例：確率10%で倍率15倍なら、期待値は 0.10 × 15 = 1.5。複勝とワイドは、オッズの幅の低い方で計算しています。</p>""")

if not s:
    st.info("過去データの集計がまだないので、ここから下の傾向の数字は次の更新で入ります。")
    st.stop()


def rows(d: dict, labels: dict | None = None) -> list:
    return [((labels or {}).get(k, k), v) for k, v in d.items()]


st.markdown(ui.section("1. 人気（単勝オッズの順）"), unsafe_allow_html=True)
pop_label = {str(i): f"{i}番人気" for i in range(1, 10)} | {"10": "10番人気以下"}
c1, c2 = st.columns(2)
with c1:
    box("人気ごとの1着率", bars(rows(s["pop_win"], pop_label), 0.4)
        + f'<p class="note">1番人気の1着率は {s["fav_win"]:.0%}。人気は多くの人の予想を集めたものなので、とても良い目安です。</p>')
with c2:
    box("人気ごとの3着内率", bars(rows(s["pop_top3"], pop_label), 0.8)
        + '<p class="note">複勝（3着以内）なら、1番人気は3回に2回ほど当たります。</p>')
box("人気ごとの単勝の回収率（100円を全部買い続けた場合）", bars(rows(s["pop_win_roi"], pop_label), 1.2)
    + '<p class="note">どの人気を買い続けても、回収率は100%を下回ります。人気だけで買う方法では勝てない、ということです。</p>')

st.markdown(ui.section("2. 前走と間隔"), unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    box("前走の着順ごとの3着内率", bars(rows(s["prev_top3"]), 0.6)
        + '<p class="note">前走で上位に来た馬は、次も上位に来やすい傾向があります。</p>')
with c2:
    box("前走からの間隔ごとの3着内率", bars(rows(s["rest_top3"]), 0.4)
        + '<p class="note">半年以上休んだ馬は割り引いて考えるのが基本です。</p>')

st.markdown(ui.section("3. 騎手と馬体重"), unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    box("騎手の勝率で5つに分けたときの3着内率", bars(rows(s["jockey_top3"]), 0.5)
        + '<p class="note">上手な騎手には良い馬も集まるので、差ははっきり出ます。</p>')
with c2:
    box("馬体重の増減ごとの3着内率", bars(rows(s["bw_top3"]), 0.4)
        + '<p class="note">大きく減った馬は調子落ちのことも。増減が小さい馬が安定しています。</p>')

st.markdown(ui.section("4. 枠（内と外）"), unsafe_allow_html=True)
c1, c2 = st.columns(2)
waku_label = {str(i): ui.chip(i, i) + f" {i}枠" for i in range(1, 9)}
for col, surf in zip((c1, c2), ("芝", "ダート")):
    if surf in s["waku_top3"]:
        with col:
            box(f"{surf}：枠ごとの3着内率", bars(rows(s["waku_top3"][surf], waku_label), 0.4)
                + '<p class="note">競艇ほど枠の差は大きくありません。コースや距離によって有利な枠が変わります。</p>')

st.markdown(ui.section("5. 荒れるレース"), unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    box("3連単の払戻（100円あたり）", f"""
{ui.kpi("真ん中の値", f"{s['tri_median']:,}円")}
<div style="height:8px"></div>
{ui.kpi("1番人気が勝ったときの真ん中", f"{s['tri_median_fav_won']:,}円")}
<div style="height:8px"></div>
{ui.kpi("1番人気が負けたときの真ん中", f"{s['tri_median_fav_lost']:,}円", "good")}
<p class="note">1番人気が負けると、配当は大きく跳ね上がります。</p>""")
with c2:
    box("1番人気の1着率（頭数ごと）", bars(rows(s["fav_win_by_field"]), 0.5)
        + '<p class="note">頭数が多いレースほど、1番人気でも勝ちにくくなります。</p>')
box("1番人気の1着率（クラスごと）", bars(rows(s["fav_win_by_class"]), 0.5)
    + '<p class="note">クラスによって、人気どおりに決まりやすいかどうかが変わります。</p>')

st.markdown(ui.section("知っておきたいこと"), unsafe_allow_html=True)
box("回収率の現実", """
<ul>
<li>馬券の売上のうち、単勝・複勝は20%、馬連・ワイドは22.5%、馬単・3連複は25%、3連単は27.5%が主催者の取り分です。何も考えずに買うと、平均で100円が75〜80円ほどになります。</li>
<li>当たりやすい順に買うだけでは、回収率は100%を超えにくいのが普通です。</li>
<li>プラスを目指すなら、オッズと比べて期待値の高い買い目だけを選び、なければ見送るのが基本です。</li>
<li>馬券は20歳になってから。余裕のあるお金で、無理のない範囲で楽しんでください。</li>
</ul>""")
