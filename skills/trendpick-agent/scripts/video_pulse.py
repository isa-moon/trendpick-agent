#!/usr/bin/env python3
"""热点选题助手 · TrendPick Agent — 海外话题脉搏（仅标准库）。

海外没有逐日热榜，用「最近 N 天按国家搜到的视频」做代理：发布量和播放量集中在哪几周、
头部视频是谁发的、品牌号占比多少。输入是 KOX `search-video --format json` 的输出文件。

用法：
  kox search-video --platform tiktok --query "back to school" --locations "AE,SA" \
      --days 30 --sort views --page-size 20 --format json > raw/back_to_school.json
  python3 video_pulse.py raw/*.json [--asof YYYY-MM-DD] [--brand-words "official|motors|auto"]

文件名（去掉扩展名）当作话题名。
"""
import argparse, json, os, re, statistics
from collections import defaultdict
from datetime import date, datetime, timedelta


def load_items(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, ""
    query = (d.get("params") or {}).get("query", "") if isinstance(d, dict) else ""
    r = d.get("result", d)
    data = r.get("data", r) if isinstance(r, dict) else r
    return (data.get("items", []) if isinstance(data, dict) else data), query


def word_pattern(w):
    """拉丁字母词按词边界匹配，词内空格可有可无（"desert camping" 能命中 #desertcamping，
    "cat" 不会命中 "catch"，"tank" 不会命中 "thank"）；#开头只匹配标签；其他文字按子串。"""
    w = w.strip().lower()
    if w.startswith("#"):
        return re.compile("#" + re.escape(w[1:]).replace(r"\ ", "") + r"(?![\w])")
    if re.fullmatch(r"[a-z0-9 ]+", w):
        body = r"[\s_]*".join(re.escape(x) for x in w.split())
        return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])")
    return re.compile(re.escape(re.sub(r"\s", "", w)))


def on_topic(it, pats):
    """KOX 视频搜索是语义相关度排序，不是精确匹配：搜一个节日名，常常会返回不相干的提车、开箱视频。
    描述里出现查询词（命中任一词组即可）才算真命中。"""
    text = (it.get("description") or it.get("title") or "").lower()
    squeezed = re.sub(r"\s", "", text)
    return any(p.search(text) or p.search(squeezed) for p in pats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--asof", default=str(date.today()))
    ap.add_argument("--brand-words", default="official|motors?|auto|cars?|dealer|showroom|brand|store|shop|mall|group|llc|ksa_|uae_")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--must", action="append", default=[],
                    help="话题=词1|词2，覆盖默认命中词（默认用查询词本身）")
    a = ap.parse_args()
    asof = date.fromisoformat(a.asof)
    brand_pat = re.compile(a.brand_words, re.I)

    print(f"# 海外话题脉搏｜截至 {asof}")
    print("话题\t命中/返回\t播放中位数\t播放合计\t发布分布（W=每 7 天，M=每 4 周，0 = 最近）\t品牌号占比\t地区（只统计真命中）")
    must = dict(m.split("=", 1) for m in a.must if "=" in m)
    detail = []
    for p in a.files:
        items, query = load_items(p)
        name = os.path.splitext(os.path.basename(p))[0]
        if items is None:
            print(f"{name}\t（文件不是有效 JSON，可能是报错信息）")
            continue
        if not items:
            print(f"{name}\t0/0\t（无结果：KOX 对阿拉伯语等非拉丁文字检索基本返回空，换英语词或改用其他渠道）")
            continue
        pats = [word_pattern(w) for w in (must.get(name) or query or name.replace("_", " ")).split("|") if w.strip()]
        returned = len(items)
        items = [it for it in items if on_topic(it, pats)]
        if not items:
            print(f"{name}\t0/{returned}\t（返回的都不是这个话题）")
            continue
        regions, ages = defaultdict(int), []
        plays, brand = [], 0
        for it in items:
            ts = it.get("create_at") or ""
            try:
                ages.append(max((asof - datetime.fromisoformat(ts.replace("Z", "+00:00")).date()).days, 0))
            except ValueError:
                pass
            plays.append(int(it.get("play_count") or 0))
            regions[it.get("region") or (it.get("author") or {}).get("country") or "?"] += 1
            who = f"{it.get('author_unique_id', '')} {it.get('author_nickname', '')}"
            if brand_pat.search(who):
                brand += 1
        # 近 8 周内按周分桶，更久的检索（如 --days 365）按 4 周分桶，不丢条目
        size, unit = (7, "W") if not ages or max(ages) < 56 else (28, "M")
        buckets = defaultdict(int)
        for g in ages:
            buckets[g // size] += 1
        n = max(buckets, default=0)
        dist = f"{unit}{n}→{unit}0: " + " ".join(str(buckets.get(k, 0)) for k in range(n, -1, -1))
        reg = " ".join(f"{k}×{v}" for k, v in sorted(regions.items(), key=lambda x: -x[1]))
        print(f"{name}\t{len(items)}/{returned}\t{int(statistics.median(plays)):,}\t{sum(plays):,}\t{dist}\t{brand / len(items):.0%}\t{reg}")
        if a.top:
            detail.append((name, sorted(items, key=lambda x: -int(x.get("play_count") or 0))[: a.top]))

    for name, top in detail:
        print(f"\n## {name}：播放最高的 {len(top)} 条")
        for it in top:
            desc = re.sub(r"\s+", " ", it.get("description") or it.get("title") or "")[:90]
            print(f"  {(it.get('create_at') or '')[:10]} {int(it.get('play_count') or 0):>10,} @{it.get('author_unique_id', '')}"
                  f"（{int(it.get('author_follower_count') or 0):,} 粉）{desc}")
            print(f"     {it.get('video_url', '')}")
    print("\n提示：搜索结果按播放排序且只取一页，分布反映的是「头部内容的发布时间」，不是全量发布量；"
          "W0 很少只说明近期没有爆款，不等于没人发。KOX 默认按作者去重，命中数是作者数。"
          "品牌号只按作者名识别，零售商、经销商账号可能认不出来。")


if __name__ == "__main__":
    main()
