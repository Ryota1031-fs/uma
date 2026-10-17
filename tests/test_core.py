import numpy as np
import pandas as pd

from keiba_yosou.features import add_features
from keiba_yosou.jra import race_id
from keiba_yosou.model import ticket_probs
from keiba_yosou.odds import parse_combo_odds


def test_race_id():
    assert race_id("pw01sde1005202604021120261004/60") == "2026100405040211"
    assert race_id("pw151ouS305202604071120261018Z/F5") == "2026101805040711"
    assert race_id("pw01dde0105202604071120261018/52") == "2026101805040711"


def test_ticket_probs_sum_to_one():
    wp = dict(enumerate(np.random.default_rng(0).dirichlet(np.ones(12)), start=1))
    tp = ticket_probs(wp)
    for t in ("単勝", "馬連", "馬単", "3連複", "3連単"):
        assert abs(sum(tp[t].values()) - 1) < 1e-9
    assert abs(sum(tp["複勝"].values()) - 3) < 1e-9
    assert abs(sum(tp["ワイド"].values()) - 3) < 1e-9
    assert "1-2" in tp["馬連"] and "2-1" not in tp["馬連"] and "2-1" in tp["馬単"]


def _race(rid, d, horses):
    return [{"race_id": rid, "date": d, "venue": "05", "surface": "芝", "class": "未勝利", "sex": "牡",
             "status": "", "num": i + 1, "waku": i + 1, "carried": 55.0, "horse_id": h, "jockey_id": j,
             "trainer_id": "t", "position": pos, "time": 100 + pos, "last3f": 34.0, "corner_last": pos,
             "distance": 1600, "odds": 2.0 + i}
            for i, (h, j, pos) in enumerate(horses)]


def test_features_use_only_past_races():
    rows = _race("r1", "2025-01-01", [("A", "j1", 1), ("B", "j2", 2)])
    rows += _race("r2", "2025-02-01", [("A", "j1", 2), ("B", "j2", 1)])
    rows += _race("r3", "2025-03-01", [("A", "j1", np.nan), ("B", "j2", np.nan)])  # これから走るレース
    f = add_features(pd.DataFrame(rows)).set_index(["race_id", "horse_id"])
    assert f.loc[("r1", "A"), "h_starts"] == 0 and np.isnan(f.loc[("r1", "A"), "h_win_rate"])
    assert f.loc[("r2", "A"), "h_win_rate"] == 1.0  # 1走目の1着だけを見ている
    assert f.loc[("r3", "A"), "h_win_rate"] == 0.5
    assert f.loc[("r3", "B"), "h_last_pos"] == 1
    # 騎手の成績も前の日までだけ
    assert f.loc[("r1", "A"), "j_starts"] == 0 and f.loc[("r3", "A"), "j_starts"] == 2


def test_parse_combo_odds():
    html = """<table class="umaren"><caption>1</caption><tbody>
    <tr><th>2</th><td>12.3</td></tr><tr><th>3</th><td><strong>4.5</strong></td></tr></tbody></table>
    <ul><li><div class="p_line"><div class="num">3</div></div><div class="p_line"><div class="num">1</div></div>
    <table class="tan3"><tbody><tr><th>2</th><td>101.0</td></tr></tbody></table></li></ul>"""
    assert parse_combo_odds(html, "馬連") == {"1-2": 12.3, "1-3": 4.5}
    assert parse_combo_odds(html, "3連単") == {"3-1-2": 101.0}
