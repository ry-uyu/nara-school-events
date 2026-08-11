# nara-school-events

娘の中学受験イベントを自動監視し、スマホ通知＋iPhoneカレンダー登録を半自動化する仕組み。

## 志望校
- 奈良女子大学附属中等教育学校
- 奈良学園登美ヶ丘中学校
- 奈良学園中学校（大和郡山）
- ＋ 上記が参加する合同説明会・進学相談会

## 仕組み
毎週、クラウドの定期エージェントが各校・塾・合同フェアの公式ページを巡回 → 新規/変更イベントを検出 → **Pushoverでスマホ通知** → 通知内のリンクを1タップで **iPhone標準カレンダーに登録**。登録するかは自分で判断できる。

- 一覧ダッシュボード（スマホ閲覧用）: https://ry-uyu.github.io/nara-school-events/
- 予定表まるごと購読（任意）: https://ry-uyu.github.io/nara-school-events/calendar.ics

## 構成
| ファイル | 役割 |
|---|---|
| `state/events.json` | 既知イベントの状態（差分判定の基準） |
| `build.py` | events.json → `docs/`（.ics・購読フィード・ダッシュボード）を生成 |
| `docs/` | GitHub Pagesで公開される配信物（自動生成、直接編集しない） |
| `AGENT.md` | クラウド定期エージェントの動作手順書 |

## 手動で再生成する場合
```bash
export PAGES_BASE_URL="https://ry-uyu.github.io/nara-school-events"
python3 build.py
```

## 注意
掲載は自動収集のため、参加申込・来場前に必ず各校の公式ページで最終確認すること。
