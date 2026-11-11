#!/usr/bin/env python3
"""杉並区議会 会議録検索システムから会議録を取得する(非公式・個人利用向け)。

使い方:
    python3 fetch.py                 # 2023年〜今年
    python3 fetch.py --from 2019     # 範囲を広げる
    python3 fetch.py --limit 5       # お試しで5件だけ

- 標準ライブラリのみで動きます。
- 取得済みの会議録(raw/<FINO>.html)は再取得しません。途中で止めても再実行で続きから。
- サーバーに負荷をかけないよう、1件ごとに --delay 秒(既定3秒)待ちます。
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://suginami.gijiroku.com/voices/voices/cgi/voiweb.exe"
UA = "suginami-gijiroku-unofficial-viewer/0.1 (personal low-rate archiver)"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
INDEX = os.path.join(HERE, "index.json")
KINDS = {1: "定例会", 2: "臨時会", 3: "委員会"}

ROW_RE = re.compile(
    r"</A>\s*([^<]*?),<A HREF=\"javascript:;\"[^>]*onClick=\"winopen\('([^']+)'\);\">([^<]*)</A>",
    re.I,
)
HIT_RE = re.compile(r"(\d+)件の日程")


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            time.sleep(10 * (i + 1))
    raise last


def list_year(year, kgtp):
    url = (
        f"{BASE}?ACT=100&KTYP=0,1,2,3&SORT=0&FYY={year}&FMM=&FDD="
        f"&TYY={year}&TMM=&TDD=&KGTP={kgtp}"
    )
    text = get(url).decode("cp932", errors="replace")
    rows = []
    for name, href, sub in ROW_RE.findall(text):
        href = href.replace("&amp;", "&")
        fino = re.search(r"FINO=(\d+)", href)
        if not fino:
            continue
        unid = re.search(r"UNID=([^&']+)", href)
        md = re.match(r"(\d+)月(\d+)日-(.*)", sub.strip())
        rows.append(
            {
                "fino": int(fino.group(1)),
                "unid": unid.group(1) if unid else "",
                "kind": KINDS[kgtp],
                "name": name.strip(),
                "sub": sub.strip(),
                "date": f"{year}-{int(md.group(1)):02d}-{int(md.group(2)):02d}" if md else f"{year}",
                "no": md.group(3) if md else "",
            }
        )
    hit = HIT_RE.search(text)
    expected = int(hit.group(1)) if hit else 0
    if expected != len(rows):
        print(f"  ! {year}年 {KINDS[kgtp]}: 表示{expected}件に対し{len(rows)}件を認識", file=sys.stderr)
    return rows


def main():
    this_year = datetime.date.today().year
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=2023)
    ap.add_argument("--to", dest="y1", type=int, default=this_year)
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=0, help="今回取得する最大件数(0=無制限)")
    a = ap.parse_args()
    delay = max(a.delay, 1.0)
    os.makedirs(RAW, exist_ok=True)

    index = {}
    if os.path.exists(INDEX):
        with open(INDEX, encoding="utf-8") as f:
            index = {d["fino"]: d for d in json.load(f)}

    print(f"一覧を取得: {a.y0}〜{a.y1}年")
    for year in range(a.y1, a.y0 - 1, -1):
        for kgtp in (1, 2, 3):
            rows = list_year(year, kgtp)
            for r in rows:
                index[r["fino"]] = r
            print(f"  {year}年 {KINDS[kgtp]}: {len(rows)}件")
            time.sleep(delay)
    docs = sorted(index.values(), key=lambda d: (d["date"], d["fino"]), reverse=True)
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=0)

    todo = [d for d in docs if not os.path.exists(os.path.join(RAW, f"{d['fino']}.html"))]
    if a.limit:
        todo = todo[: a.limit]
    print(f"会議録 {len(docs)}件中、未取得 {len(todo)}件を取得します(約{len(todo) * (delay + 1) / 60:.0f}分)")
    fails = 0
    for i, d in enumerate(todo, 1):
        url = f"{BASE}?ACT=203&FINO={d['fino']}&HATSUGENMODE=1&HYOUJIMODE=0&STYLE=0"
        path = os.path.join(RAW, f"{d['fino']}.html")
        try:
            body = get(url)
            if b"HUID" not in body:
                raise ValueError("本文が見つかりません")
            with open(path + ".part", "wb") as f:
                f.write(body)
            os.replace(path + ".part", path)
            fails = 0
            print(f"[{i}/{len(todo)}] {d['date']} {d['name']} {d['no']} ({len(body) // 1024}KB)")
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"[{i}/{len(todo)}] 失敗 FINO={d['fino']}: {e}", file=sys.stderr)
            if fails >= 5:
                sys.exit("5件連続で失敗したため中断しました。時間をおいて再実行してください。")
        time.sleep(delay)
    print("完了。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中断しました。再実行すると続きから取得します。")
