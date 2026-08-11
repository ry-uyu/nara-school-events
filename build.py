#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
state/events.json を読み、docs/ 以下に配信物を生成する。
  - docs/e/<id>.ics          … イベント1件ごとの .ics（iPhoneで1タップ追加用）
  - docs/e/<id>-apply.ics    … 申込開始日の .ics（apply_start がある場合）
  - docs/calendar.ics        … 全イベントまとめの購読用フィード
  - docs/index.html          … 一覧ダッシュボード（スマホ閲覧用）
依存ライブラリなし（標準ライブラリのみ）。
"""
import json
import os
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "state", "events.json")
DOCS = os.path.join(ROOT, "docs")
EDIR = os.path.join(DOCS, "e")
JST = timezone(timedelta(hours=9))

# GitHub Pages のベースURL（リポジトリ公開後に build 時点で確定させる）
BASE_URL = os.environ.get("PAGES_BASE_URL", "").rstrip("/")


def today_jst():
    return datetime.now(JST).date()


CLOSED_MARKS = ("満席", "受付終了", "受付を終了", "募集終了", "締切", "終了しました")


def is_closed(ev, today):
    """満席・受付終了・申込締切超過なら True（ダッシュボード掲載対象外）。"""
    st = ev.get("status") or ""
    if any(k in st for k in CLOSED_MARKS):
        return True
    dl = ev.get("apply_deadline")
    if dl:
        try:
            if datetime.strptime(dl, "%Y-%m-%d").date() < today:
                return True
        except ValueError:
            pass
    return False


def ics_escape(s):
    if s is None:
        return ""
    return (str(s).replace("\\", "\\\\").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


def fold(line):
    """75オクテット超の行を折り返す（RFC5545）。"""
    b = line.encode("utf-8")
    if len(b) <= 73:
        return line
    out, cur = [], b""
    for ch in line:
        chb = ch.encode("utf-8")
        if len(cur) + len(chb) > 73:
            out.append(cur.decode("utf-8"))
            cur = b" " + chb
        else:
            cur += chb
    out.append(cur.decode("utf-8"))
    return "\r\n".join(out)


def dtstamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def school(schools, key):
    return schools.get(key, {"name": key, "short": key, "color": "#555"})


def event_description(ev, sc):
    parts = [f"種別: {ev.get('type','')}", f"学校/主催: {sc['name']}"]
    if ev.get("date_raw"):
        t = ev["date_raw"]
        if not ev.get("all_day") and ev.get("start_time"):
            t += f" {ev['start_time']}"
            if ev.get("end_time"):
                t += f"〜{ev['end_time']}"
        parts.append(f"日時: {t}")
    if ev.get("location"):
        parts.append(f"場所: {ev['location']}")
    if ev.get("reservation_note"):
        parts.append(f"予約: {ev['reservation_note']}")
    if ev.get("apply_start"):
        parts.append(f"申込開始: {ev['apply_start']}")
    if ev.get("apply_deadline"):
        parts.append(f"申込締切: {ev['apply_deadline']}")
    if ev.get("note"):
        parts.append(f"メモ: {ev['note']}")
    if ev.get("url"):
        parts.append(f"詳細: {ev['url']}")
    return "\\n".join(ics_escape(p) for p in parts)


def vevent(uid, summary, date_str, all_day, start_time, end_time,
           location, description, url):
    """1件の VEVENT 文字列を返す。date_str は YYYY-MM-DD。"""
    y, m, d = date_str.split("-")
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{dtstamp()}"]
    if all_day or not start_time:
        lines.append(f"DTSTART;VALUE=DATE:{y}{m}{d}")
        end = (datetime(int(y), int(m), int(d)) + timedelta(days=1))
        lines.append(f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}")
    else:
        sh, sm = start_time.split(":")
        lines.append(f"DTSTART:{y}{m}{d}T{sh}{sm}00")
        if end_time:
            eh, em = end_time.split(":")
            lines.append(f"DTEND:{y}{m}{d}T{eh}{em}00")
        else:
            eh = f"{(int(sh)+1) % 24:02d}"
            lines.append(f"DTEND:{y}{m}{d}T{eh}{sm}00")
    lines.append(f"SUMMARY:{ics_escape(summary)}")
    if location:
        lines.append(f"LOCATION:{ics_escape(location)}")
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if url:
        lines.append(f"URL:{ics_escape(url)}")
    lines.append("END:VEVENT")
    return "\r\n".join(fold(l) for l in lines)


def wrap_calendar(vevents):
    head = ["BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//nara-school-events//JP", "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH", "X-WR-CALNAME:中学受験イベント",
            "X-WR-TIMEZONE:Asia/Tokyo"]
    return "\r\n".join(head + vevents + ["END:VCALENDAR"]) + "\r\n"


def build_event_vevent(ev, sc):
    return vevent(
        uid=f"{ev['id']}@nara-school-events",
        summary=f"【{sc['short']}】{ev['title']}",
        date_str=ev["date"], all_day=ev.get("all_day", False),
        start_time=ev.get("start_time"), end_time=ev.get("end_time"),
        location=ev.get("location", ""),
        description=event_description(ev, sc), url=ev.get("url", ""))


def build_apply_vevent(ev, sc):
    desc = (f"{ics_escape(sc['short'])}「{ics_escape(ev['title'])}」の"
            f"申込開始日です。\\n本番: {ev.get('date_raw','')}\\n"
            f"詳細: {ics_escape(ev.get('url',''))}")
    return vevent(
        uid=f"{ev['id']}-apply@nara-school-events",
        summary=f"【申込開始】{sc['short']} {ev['title']}",
        date_str=ev["apply_start"], all_day=True, start_time=None,
        end_time=None, location=ev.get("location", ""),
        description=desc, url=ev.get("url", ""))


def html_dashboard(events, schools, base):
    rows = []
    for ev in events:
        sc = school(schools, ev["school_key"])
        when = ev.get("date_raw", ev.get("date", ""))
        if not ev.get("all_day") and ev.get("start_time"):
            when += f" {ev['start_time']}"
            if ev.get("end_time"):
                when += f"〜{ev['end_time']}"
        badges = []
        if ev.get("apply_start"):
            badges.append(f'<span class="badge apply">申込開始 {ev["apply_start"]}</span>')
        if ev.get("apply_deadline"):
            badges.append(f'<span class="badge dl">締切 {ev["apply_deadline"]}</span>')
        if ev.get("reservation_required"):
            badges.append('<span class="badge res">要予約</span>')
        add_ev = f'{base}/e/{ev["id"]}.ics' if base else f'e/{ev["id"]}.ics'
        btns = [f'<a class="btn add" href="{add_ev}">＋ カレンダー追加</a>']
        if ev.get("apply_start"):
            add_ap = f'{base}/e/{ev["id"]}-apply.ics' if base else f'e/{ev["id"]}-apply.ics'
            btns.append(f'<a class="btn apply" href="{add_ap}">＋ 申込開始日</a>')
        if ev.get("url"):
            btns.append(f'<a class="btn link" href="{ev["url"]}" target="_blank" rel="noopener">詳細 ↗</a>')
        rows.append(f'''
      <div class="card">
        <div class="chip" style="--c:{sc['color']}">{sc['short']}</div>
        <div class="body">
          <div class="date">{when}</div>
          <div class="title">{ev['title']}</div>
          <div class="meta">{ev.get('type','')}{' ・ ' + ev['location'] if ev.get('location') else ''}</div>
          <div class="badges">{''.join(badges)}</div>
          {'<div class="note">' + ev['note'] + '</div>' if ev.get('note') else ''}
          <div class="btns">{''.join(btns)}</div>
        </div>
      </div>''')
    sub = f'{base}/calendar.ics' if base else 'calendar.ics'
    webcal = sub.replace("https://", "webcal://").replace("http://", "webcal://")
    updated = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    return f'''<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中学受験イベント</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--tx:#1a1d22;--sub:#5b6470;--line:#e6e9ee;}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12151a;--card:#1b1f27;--tx:#eef1f5;--sub:#9aa4b2;--line:#2a2f3a;}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.5}}
header{{padding:20px 16px 8px;max-width:720px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{color:var(--sub);font-size:13px}}
.subscribe{{display:inline-block;margin-top:10px;font-size:13px;color:#2563eb;text-decoration:none;border:1px solid var(--line);padding:6px 10px;border-radius:8px}}
main{{max-width:720px;margin:0 auto;padding:8px 12px 60px}}
.card{{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin:10px 0}}
.chip{{flex:0 0 auto;align-self:flex-start;font-size:11px;font-weight:700;color:#fff;background:var(--c);padding:4px 8px;border-radius:999px;white-space:nowrap}}
.body{{flex:1;min-width:0}}
.date{{font-size:13px;color:var(--sub);font-weight:600}}
.title{{font-size:16px;font-weight:700;margin:2px 0}}
.meta{{font-size:13px;color:var(--sub)}}
.badges{{margin:6px 0}}
.badge{{display:inline-block;font-size:11px;padding:2px 7px;border-radius:6px;margin:2px 4px 2px 0}}
.badge.apply{{background:#fde68a;color:#7a5b00}}
.badge.dl{{background:#fecaca;color:#8a1c1c}}
.badge.res{{background:#dbeafe;color:#1e40af}}
.note{{font-size:12px;color:var(--sub);margin:4px 0}}
.btns{{margin-top:8px;display:flex;flex-wrap:wrap;gap:8px}}
.btn{{font-size:13px;text-decoration:none;padding:8px 12px;border-radius:9px;border:1px solid var(--line)}}
.btn.add{{background:#2563eb;color:#fff;border-color:#2563eb}}
.btn.apply{{background:#f59e0b;color:#fff;border-color:#f59e0b}}
.btn.link{{color:var(--tx)}}
footer{{max-width:720px;margin:0 auto;padding:0 16px 40px;color:var(--sub);font-size:12px}}
</style></head>
<body>
<header>
  <h1>娘の中学受験イベント</h1>
  <div class="sub">奈良女子大附属 / 奈良学園登美ヶ丘 / 奈良学園 ＋ 合同説明会　｜　更新: {updated}</div>
  <a class="subscribe" href="{webcal}">📅 この予定表をまるごと購読（任意）</a>
</header>
<main>
{''.join(rows) if rows else '<p>今後の予定はまだありません。</p>'}
</main>
<footer>各「＋ カレンダー追加」を押すとiPhoneの標準カレンダーに1件だけ追加できます。掲載は自動収集のため、参加前に必ず公式ページで最終確認してください。</footer>
</body></html>
'''


def main():
    with open(STATE, encoding="utf-8") as f:
        data = json.load(f)
    schools = data.get("schools", {})
    today = today_jst()
    os.makedirs(EDIR, exist_ok=True)

    # 未来（今日以降）かつ日付ありのイベントのみ配信対象
    upcoming = []
    for ev in data.get("events", []):
        if not ev.get("date"):
            continue
        try:
            d = datetime.strptime(ev["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= today and not is_closed(ev, today):
            upcoming.append((d, ev))
    upcoming.sort(key=lambda x: (x[0], x[1].get("start_time") or "00:00"))
    ordered = [ev for _, ev in upcoming]

    feed = []
    n_ics = 0
    for ev in ordered:
        sc = school(schools, ev["school_key"])
        ve = build_event_vevent(ev, sc)
        with open(os.path.join(EDIR, f"{ev['id']}.ics"), "w",
                  encoding="utf-8", newline="") as f:
            f.write(wrap_calendar([ve]))
        feed.append(ve)
        n_ics += 1
        if ev.get("apply_start"):
            ap = build_apply_vevent(ev, sc)
            with open(os.path.join(EDIR, f"{ev['id']}-apply.ics"), "w",
                      encoding="utf-8", newline="") as f:
                f.write(wrap_calendar([ap]))
            # 申込開始日が未来なら購読フィードにも入れる
            try:
                ad = datetime.strptime(ev["apply_start"], "%Y-%m-%d").date()
                if ad >= today:
                    feed.append(ap)
            except ValueError:
                pass

    with open(os.path.join(DOCS, "calendar.ics"), "w",
              encoding="utf-8", newline="") as f:
        f.write(wrap_calendar(feed))

    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_dashboard(ordered, schools, BASE_URL))

    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print(f"[build] upcoming={len(ordered)} ics_files={n_ics} "
          f"feed_events={len(feed)} base={BASE_URL or '(relative)'}")


if __name__ == "__main__":
    main()
