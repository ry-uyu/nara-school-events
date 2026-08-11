# AGENT.md — クラウド定期エージェントの動作手順（v2）

このリポジトリは「娘の中学受験イベント」を自動監視し、更新をPushover通知し、iPhoneカレンダーに1タップで追加できる.icsを配信する。**あなた（スケジュール実行エージェント）は毎回この手順を上から順に厳密に実行すること。**

## 実行タイミング
1日2回：**07:00 / 17:00 JST**（cron `0 8,22 * * *` UTC）。

## 大前提
- 志望3校（`tier=="priority"`）：奈良女子大学附属中等教育学校 / 奈良学園登美ヶ丘中学校 / 奈良学園中学校（大和郡山）。**毎回巡回**。
- その他の県内私立中・合同説明会（`tier=="weekly"`）：**日曜朝の回だけ巡回**。
- 対象は中学受験（中等教育学校前期含む）関連のみ。高校専用は無視。
- Pushover認証は環境変数 `PUSHOVER_TOKEN` / `PUSHOVER_USER`。**絶対にコミット・出力しない。**
- GitHub Pages: `https://ry-uyu.github.io/nara-school-events`

## この実行の種別を決める
```
WD=$(TZ=Asia/Tokyo date +%u)   # 1=月 .. 7=日
HH=$(TZ=Asia/Tokyo date +%H)
TODAY=$(TZ=Asia/Tokyo date +%F)
```
- **週次実行** = （`WD==7` かつ `HH==07`）＝日曜朝の回だけ。→ 全ソース（priority＋weekly）を巡回し、最後に週次通知を必ず1通送る。
- **通常実行** = それ以外の回。→ priorityソースのみ巡回。更新があれば即通知、無ければ何も送らない。

## 手順

### 1. 状態を読む
- `state/events.json` … 既知イベント（差分判定の基準）。`schools` に `tier` あり。
- `state/sources.json` … 各ソースURL→前回の内容ハッシュ。無ければ空 `{}` として扱う。

### 2. 巡回対象ソースを決める
- 通常実行：`schools[*]` のうち `tier=="priority"` の `sources` のみ。
- 週次実行：全 `schools[*].sources`（priority＋weekly）。加えて WebSearch で「奈良県 私立中学 説明会 <当月>」等を1〜2回だけ検索し、県内その他私立中の新着も拾う。

### 3. 変更ページのみ抽出（★トークン節約の要）
対象URLごとに、まず**LLMを使わずBashで**内容ハッシュを取る：
```
BODY=$(curl -sL --max-time 30 "$URL")
HASH=$(printf '%s' "$BODY" | python3 -c "import sys,re,hashlib; t=sys.stdin.read(); t=re.sub(r'<script.*?</script>','',t,flags=re.S|re.I); t=re.sub(r'<style.*?</style>','',t,flags=re.S|re.I); t=re.sub(r'<[^>]+>',' ',t); t=re.sub(r'\\s+',' ',t); print(hashlib.sha256(t.encode('utf-8','ignore')).hexdigest())")
```
- `state/sources.json` の前回ハッシュと**一致 → そのページは変化なし。本文をLLMで読まずスキップ。**
- **不一致（または初回）** → そのページだけ WebFetch で本文を取得し、中学受験関連イベントを抽出。
- 取得後、新しいハッシュを `state/sources.json` に保存。

**抽出項目**：`title` / `type`（学校見学会・説明会・オープンスクール・オープンキャンパス・文化祭・入試説明会・合同説明会・願書受付・受験日程・その他）/ `date`（`YYYY-MM-DD`、未発表は `null`）/ `date_raw` / `start_time` / `end_time` / `all_day` / `location` / `reservation_required` / `reservation_note` / `apply_start` / `apply_deadline` / `url` / `source`。
**鉄則**：ページに明記された情報のみ（推測禁止、読めなければ `null`）。和暦・曜日つき表記を正しくISO化。高校専用は除外。

**最重要（志望3校では絶対に取りこぼさない）**：`学校見学会` / `説明会（入試説明会含む）` / `願書受付（出願受付）` / `受験日程（入試日・適性検査日）`。この4種は `type` を正確に付ける。

### 4. state/events.json にマージ
- `id = "{school_key}-{titleを英数slug化}-{date or 'tbd'}"`（毎回一意。既存に一致候補があればその `id` を再利用）。
- **新規**＝基準にidが無い。**変更**＝既存idの `date`/`start_time`/`location`/`apply_start`/`apply_deadline` のいずれかが変化。
- `first_seen`/`last_updated` を設定。過去日・`date:null` も保持（履歴）。`meta.last_run`=`TODAY`。

### 5. 配信物生成 → コミット
```
export PAGES_BASE_URL="https://ry-uyu.github.io/nara-school-events"
python3 build.py
# 差分がある時のみ:
git add -A && git commit -m "update: $TODAY 新規N/変更M" && git push origin HEAD:main
```
認証情報は絶対にコミットしない。

### 6. 通知

**A. 即時通知（毎回・志望3校の更新）**
priority校に今回の新規/変更が1件以上 → その場でPushover送信。
- 種別が最重要4種（見学会/説明会/願書受付/受験日程）→ `priority=1`、本文先頭に「⚡最重要」。
- 日付が「未発表→確定」に変わった → 「⚡確定」。日程が動いた → 「⚠日程変更」。
- 1〜3件は個別送信（`url`=該当.icsの絶対URL `https://ry-uyu.github.io/nara-school-events/e/{id}.ics`、`url_title="カレンダーに追加"`）。4件以上はまとめて1通（`url`=ダッシュボード、`url_title="一覧を開く"`）。

**B. 週次通知（週次実行のときだけ・必ず1通）**
- weekly校（県内その他私立＋合同）の新規/変更を本文にまとめる。
- 直近7日以内に `last_updated` が更新された全イベントを「今週の更新」として簡潔に要約。
- 直近7日で更新が1件も無ければ「📭 今週は更新なし（監視は正常稼働）」を送る（＝生存確認）。
- `url`=ダッシュボード、`url_title="一覧を開く"`。

**C. サイレント**
通常実行で今回の新規/変更が0件 → 何も送らない（コミットも不要）。

Pushover送信コマンド：
```
curl -s --form-string "token=$PUSHOVER_TOKEN" --form-string "user=$PUSHOVER_USER" \
  --form-string "title=TITLE" --form-string "message=MESSAGE" \
  --form-string "url=URL" --form-string "url_title=カレンダーに追加" \
  [--form-string "priority=1"] \
  https://api.pushover.net/1/messages.json
```
本文には必ず「学校名・日付・種別・要予約/申込開始」を含める。簡潔に。

### 7. 実行サマリ
「巡回N / スキップ(ハッシュ一致)N / 新規N / 変更N / 即時通知N件 / 週次通知(有無)」を1行で標準出力に残す。

## ポリシー
- 迷ったら通知しない側に倒す。ただし志望3校の最重要4種は絶対に取りこぼさない。
- 重複通知は避ける（既に即時通知済みの項目を週次で再掲するのは可、ただし「今週のまとめ」であることを明示）。
- ハルシネーション厳禁。ページに明記された情報のみ。
