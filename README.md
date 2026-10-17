# 競馬予想（試作）

JRA公式サイトの出馬表・レース結果・オッズから各馬の1着確率を出し、単勝・複勝・ワイド・馬連・馬単・3連複・3連単の買い目確率と、オッズと比べた期待値を表示する自分用のWebアプリ。

## 使い方
```bash
pip install -r requirements.txt

# 1. 過去データを取得（公式サイトの負荷を避けるため、1ページずつ間隔を空ける）
python -m keiba_yosou.download 2024-10-01 2026-10-16

# 2. オッズどおり／LightGBM（オッズなし・あり）を比べ、検証期間の的中率・回収率を出す（models/ にモデルを保存）
python -m keiba_yosou.backtest --top 5

# 3. 画面を起動
streamlit run app.py
```

## Windowsでの起動と更新
- `start.bat` をダブルクリックすると起動する（必要な部品も自動で確認する）。
- 画面左の「アプリを最新版に更新」を押すと、GitHub の最新版で上書きする。取り込んだデータ（`data/`）はそのまま残る。

## 構成
- `keiba_yosou/jra.py` JRA公式（JRADB）のページ取得。ページ内のリンク（cname）をたどる
- `keiba_yosou/download.py` 過去のレース結果と単勝・複勝の最終オッズを月ごとに取得
- `keiba_yosou/parse.py` 結果・オッズ・出馬表のページを表に変換
- `keiba_yosou/dataset.py` 取得したページを1つの表にまとめる（月ごとに data/table/ に控える）
- `keiba_yosou/features.py` 馬・騎手・調教師の過去成績などの特徴量（そのレースより前の日だけを使う）
- `keiba_yosou/model.py` オッズどおり、LightGBM、Harville法による券種ごとの確率
- `keiba_yosou/backtest.py` 日付で学習と検証に分けた的中率・回収率の集計と、画面用モデルの保存
- `keiba_yosou/live.py` 日付ごとのレース一覧・出馬表・結果の取得
- `keiba_yosou/odds.py` 締切前の全券種オッズの取得
- `keiba_yosou/predict.py` 画面から使う予想の処理
- `keiba_yosou/update.py` GitHub から最新版を取って上書きする
- `app.py`, `views/` Streamlitの画面

## 注意
- JRAのホームページの利用規定に従い、私的使用の範囲で使う。取得したページの再配布はしない（`data/` は GitHub に上げない）。
- `models/history.csv.gz` は、画面で過去成績を計算するための数値（番号・着順・タイムなど）だけを抜き出したもの。

## Discordに予想を送る
画面左の「Discord連携」に、Discordのチャンネルで作ったウェブフックのURLを保存すると、予想画面に「Discordに送る」ボタンが出ます。URLは `data/discord.json` にだけ保存され、GitHubには上がりません。投稿するのはアプリの予想（確率と買い目）と公式ページへのリンクだけです。Web版では Streamlit の Secrets に `discord_webhook_url` として入れます。
