#!/usr/bin/env python3
"""会議録の公開の遅れ(会議日 → 一覧に初めて現れた日)を集計する。

使い方:
    python3 lag.py

- fetch.py が記録する index.json の first_seen を使います。
- first_seen は「その実行で初めて見つけた日」なので、実際の公開日より
  最大で実行間隔ぶん(週1回なら最大7日)遅れて記録されます。
- 計測開始前から公開済みだった会議録には first_seen がなく、集計に含みません。
"""
import datetime
import json
import os
import re
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "index.json"), encoding="utf-8") as f:
        docs = json.load(f)
    by_seen = defaultdict(list)
    for d in docs:
        if d.get("first_seen") and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["date"]):
            by_seen[d["first_seen"]].append(d)
    if not by_seen:
        print("first_seen の記録がまだありません。fetch.py の定期実行で新しい会議録が見つかると記録されます。")
        return

    def days(d):
        return (datetime.date.fromisoformat(d["first_seen"]) - datetime.date.fromisoformat(d["date"])).days

    print("検出日      件数  会議日の範囲              遅れ(日) 最小/中央/最大")
    all_lags = []
    for seen in sorted(by_seen):
        ds = by_seen[seen]
        lags = [days(d) for d in ds]
        all_lags += lags
        dates = sorted(d["date"] for d in ds)
        print(f"{seen}  {len(ds):4d}  {dates[0]}〜{dates[-1]}  "
              f"{min(lags):4d} / {statistics.median(lags):4.0f} / {max(lags):4d}")
    print(f"\n全体 {len(all_lags)}件: 最小 {min(all_lags)}日 / 中央 {statistics.median(all_lags):.0f}日 / 最大 {max(all_lags)}日")
    print(f"公開のまとまり(検出日)の数: {len(by_seen)}回")


if __name__ == "__main__":
    main()
