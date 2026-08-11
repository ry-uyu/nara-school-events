# AGENT.md — クラウド定期エージェントの動作手順

このリポジトリは「娘の中学受験イベント」を自動監視し、新規/変更イベントをPushoverでスマホ通知し、iPhoneカレンダーに1タップで追加できる.icsを配信する。**あなた（スケジュール実行エージェント）は、毎回この手順を上から順に厳密に実行すること。**

## 大前提
- 監視対象の志望校は3校：奈良女子大学附属中等教育学校 / 奈良学園登美ヶ丘中学校 / 奈良学園中学校（大和郡山）。加えて、この3校が参加する合同説明会・進学相談会も対象。
- 対象は **中学受験（中等教育学校前期含む）** 関連イベントのみ。高校のみ対象のイベントは無視。
- Pushoverの認証情報は環境変数 `PUSHOVER_TOKEN` / `PUSHOVER_USER` から渡される。**これらを絶対にリポジトリへコミットしない。**
- GitHub PagesベースURL：`https://ry-uyu.github.io/nara-school-events`

## リポジトリ構成
- `state/events.json` … 既知イベントの唯一の状態ソース（前回までの記録＝差分判定の基準）
- `build.py` … `state/events.json` から `docs/`（.ics群・購読フィード・ダッシュボード）を生成
- `docs/` … GitHub Pagesで公開される配信物（直接編集しない。必ずbuild.pyで生成）

## 手順

### 1. 基準を読む
`state/events.json` を読む。これが「前回時点で判明していたイベント」＝差分判定の基準。イベントの一意キーは `id`。

### 2. 各ソースを巡回して最新イベントを抽出
`state/events.json` の `schools[*].sources` の各URLを取得（WebFetchを優先、失敗時は `curl -sL`）。各ページから中学受験関連イベントを抽出する。抽出項目：
- `title`（イベント名）, `type`（説明会/オープンスクール/オープンキャンパス/文化祭/入試説明会/合同説明会/受付開始/出願/入試/その他）
- `date`（`YYYY-MM-DD`。**未発表なら `null`**）, `date_raw`（原文の日付表記）
- `start_time` / `end_time`（`"HH:MM"` または null）, `all_day`（時刻不明なら true）
- `location`, `reservation_required`(bool), `reservation_note`
- `apply_start`（申込・予約の開始日 `YYYY-MM-DD` / null）, `apply_deadline`（同 締切 / null）
- `url`（詳細ページ）, `source`（どのソースか）

**抽出の鉄則（ハルシネーション厳禁）**
- ページに明記された情報のみ記録。推測で日付を作らない。読み取れなければ `null`。
- 日本語の和暦・曜日つき表記（例「9月20日（日）」）を正しくISO化。年が無ければ文脈から判断（当年〜翌年度入試）。
- 高校専用イベントは除外。3校いずれとも無関係な合同イベントは除外。

### 3. idの決定（毎回同じ結果になること）
`id = "{school_key}-{titleを英数slug化}-{date or 'tbd'}"`。同じイベントが再登場したら必ず同じidになるよう、既存 `events.json` に一致候補（同school_key＆日付近接＆タイトル類似）があればその `id` を再利用する。

### 4. state/events.json を更新
- **新規**（基準にidが無い）→ 追加。`first_seen`=今日, `last_updated`=今日。
- **変更**（idはあるが `date`/`start_time`/`location`/`apply_start`/`apply_deadline` のいずれかが変化）→ 上書き更新し `last_updated`=今日。**何がどう変わったかを覚えておく**（通知文に使う）。
- 変化なし → 触らない。
- 過去日・掲載終了イベントも `state` からは消さない（履歴）。`date:null` のイベントは保持し、後で日付が付いたら「変更」として扱う。
- `meta.last_run` を今日の日付に更新。

### 5. 配信物を生成
```
export PAGES_BASE_URL="https://ry-uyu.github.io/nara-school-events"
python3 build.py
```
`docs/` が再生成される。過去イベントは自動的に配信対象外になる。

### 6. 今回の新規/変更を確定
ステップ4で「新規」「変更」と判定したイベント群が今回の通知対象。`date:null`（日付未発表）のものは通知に含めてよいが、.icsリンクは付けない（日付が無いとカレンダー登録できないため、ダッシュボードのURLを案内）。

### 7. コミット & プッシュ
差分があれば必ず：
```
git add -A
git commit -m "update: YYYY-MM-DD 新規N件/変更M件"
git push origin HEAD:main
```
（`state/`と`docs/`のみ。認証情報ファイルは作らない。）

### 8. Pushover通知（新規/変更が1件以上のときだけ）
新規/変更が **0件なら通知しない**（プッシュもコミットメッセージも出さない。ただしbuild差分があればサイレントにコミットは可）。

送信ルール：
- **新規/変更が1〜3件**：1件ずつ個別に送る。各メッセージの `url` に **その.icsの絶対URL**、`url_title="カレンダーに追加"` を付ける。
  - `url` 例：`https://ry-uyu.github.io/nara-school-events/e/{id}.ics`
  - `apply_start` があり申込が迫る場合は、本文にその旨を明記（申込.icsは `.../e/{id}-apply.ics`）。
- **4件以上**：まとめて1通。本文に各イベントを1行ずつ列挙し、`url` はダッシュボード `https://ry-uyu.github.io/nara-school-events/`、`url_title="一覧を開く"`。

メッセージ本文フォーマット（例）：
```
title: 【中学受験】新着イベント（登美ヶ丘）
message: 9/20(日) 入試説明会 / 奈良県コンベンションセンター 要予約・申込開始9/1
```
必ず「学校名・日付・種別・要予約/申込開始」を含める。冗長にしない。

Pushover送信コマンド：
```
curl -s --form-string "token=$PUSHOVER_TOKEN" \
     --form-string "user=$PUSHOVER_USER" \
     --form-string "title=TITLE" \
     --form-string "message=MESSAGE" \
     --form-string "url=ICS_OR_DASHBOARD_URL" \
     --form-string "url_title=カレンダーに追加" \
     https://api.pushover.net/1/messages.json
```

### 9. 最後にログ出力
実行サマリ（巡回件数 / 新規 / 変更 / 通知有無）を標準出力に1行で残す。

## 変わった時のポリシー
- 日付が「未発表→確定」に変わったら最優先の通知（`type`の先頭に「⚡確定」を付ける）。
- 既存イベントの日付が動いた（延期・変更）ら「⚠日程変更」と明示。
- 迷ったら通知しない側に倒す（誤通知より取りこぼしの再送のほうがマシ、ただし重複通知は避ける）。
