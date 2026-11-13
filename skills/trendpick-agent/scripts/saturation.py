#!/usr/bin/env python3
"""饱和度检查：这个梗/节点，已经有多少品牌和商家在做。

输入是 blueai-social-media-data 导出的帖子 JSON（存量模式，按互动量排序拉取）。
只用标准库。

用法：
  python3 saturation.py <导出的 JSON> [更多 JSON] \
      --must "立冬" --category "咖啡|奶茶|拿铁|热饮" \
      --brands "星巴克|瑞幸|库迪|Manner|喜茶" --top 20

检索时只搜梗或节点的核心词（如「立冬」），不要用 + 和 | 拼组合词；
品类用 --category 在本地筛。

判定（和 judgment.md §3 一致）：
  互动量前 N 条里，品牌号 + 商家号
    ≤ 1 个  → 强（还没被做烂）
    2–5 个  → 中
    > 5 个  → 弱（已经扎堆，按顶峰处理）

注意：小红书、抖音导出数据里没有蓝 V 认证字段，品牌号靠账号名命中名单、
商家号靠账号名和简介里的商家特征词识别，都要看列出的账号人工复核。
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta

MERCHANT_NAME = re.compile(r"官方|旗舰|品牌|门店|分店|专卖|商贸|有限公司|集团|连锁|[店铺馆]$|[店铺馆][)）]|[(（].*店[)）]")
MERCHANT_DESC = re.compile(r"官方账号|官方号|品牌官方|旗舰店|门店|欢迎到店|到店|营业时间|始于\s*\d{4}|\d{4}\s*年成立|供应商|招商|加盟")
CST = timezone(timedelta(hours=8))


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def load(paths):
    docs = []
    for p in paths:
        data = json.load(open(p, encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("data") or data.get("docs") or []
        docs.extend(data)
    seen, out = set(), []
    for d in docs:
        post = d.get("post_info") or {}
        key = post.get("post_id") or post.get("url")
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def classify(author, brand_rx):
    name = author.get("user_name") or ""
    desc = author.get("user_desc") or ""
    if brand_rx and brand_rx.search(name):
        return "品牌号"
    if MERCHANT_NAME.search(name) or MERCHANT_DESC.search(desc):
        return "商家号"
    return ""


def main():
    ap = argparse.ArgumentParser(description="统计互动量前 N 条里有多少品牌号和商家号")
    ap.add_argument("files", nargs="+", help="blueai-social-media-data 导出的 JSON")
    ap.add_argument("--brands", default="", help="品牌和竞品名，用 | 分隔，如 '星巴克|瑞幸|库迪'")
    ap.add_argument("--top", type=int, default=20, help="看互动量前几条，默认 20")
    ap.add_argument("--must", default="", help="检索词本身，如 '立冬'；先报含检索词的比例，用来发现关键词写错")
    ap.add_argument("--category", default="", help="品类词，用 | 分隔，如 '咖啡|奶茶|拿铁|热饮'；只统计这些帖子")
    a = ap.parse_args()

    docs = load(a.files)
    if not docs:
        sys.exit("没有读到帖子：检查是不是 blueai-social-media-data 存量模式导出的 JSON")
    def text(d):
        p = d.get("post_info") or {}
        return " ".join(str(p.get(f) or "") for f in ("title", "content", "tags"))

    if a.must:
        # 检索词本身有没有出现：用来发现关键词写错（如 + 和 | 的组合没按预期解析）
        must_rx = re.compile(a.must, re.I)
        before = len(docs)
        docs = [d for d in docs if must_rx.search(text(d))]
        print(f"# 相关性｜标题、正文或标签含「{a.must}」：{len(docs)} / {before}")
        if before and len(docs) / before < 0.5:
            print("⚠ 不到一半的帖子含检索词：关键词可能没按预期解析。只用梗或节点的核心词重搜，品类用 --category 在本地筛")
        if not docs:
            sys.exit("没有相关帖子，无法判断饱和度")
    if a.category:
        # 品类筛选：只看和本品牌同品类的帖子，比例低是正常的，不报警
        cat_rx = re.compile(a.category, re.I)
        before = len(docs)
        docs = [d for d in docs if cat_rx.search(text(d))]
        print(f"# 品类｜其中和「{a.category}」相关：{len(docs)} / {before}")
        if not docs:
            sys.exit("这个梗或节点下没有本品类的帖子：同品类还没人做，这一维记「强」，在卡片上写明检索词、条数和日期")
    brand_rx = re.compile(a.brands, re.I) if a.brands else None
    docs.sort(key=lambda d: to_int((d.get("post_info") or {}).get("interaction_cnt")), reverse=True)
    top = docs[: a.top]

    rows, brand_n, merchant_n = [], 0, 0
    for i, d in enumerate(top, 1):
        post, author = d.get("post_info") or {}, d.get("author_info") or {}
        kind = classify(author, brand_rx)
        brand_n += kind == "品牌号"
        merchant_n += kind == "商家号"
        ts = to_int(post.get("publish_time"))
        day = datetime.fromtimestamp(ts, CST).strftime("%m-%d") if ts else "--"
        rows.append((i, kind, to_int(post.get("interaction_cnt")), day,
                     (author.get("user_name") or "")[:16], (post.get("title") or "")[:28], post.get("url") or ""))

    hit = brand_n + merchant_n
    verdict = "强（还没被做烂）" if hit <= 1 else ("中" if hit <= 5 else "弱（已经扎堆，按顶峰处理）")
    print(f"# 饱和度｜共 {len(docs)} 条，看互动量前 {len(top)} 条")
    print(f"品牌号 {brand_n} 个，商家号 {merchant_n} 个，合计 {hit} 个 → 没被做烂：{verdict}")
    if not brand_rx:
        print("⚠ 没传 --brands：品牌号只能靠商家特征词识别，会漏掉品牌官方号。把品牌和竞品名单传进来再跑")
    print("⚠ 导出数据没有蓝 V 字段，下面标了「品牌号」「商家号」的账号要逐个看一眼，误判就剔除后重算")
    print()
    print("排名\t类型\t互动\t日期\t账号\t标题\t链接")
    for r in rows:
        print("\t".join(str(x) for x in r))


if __name__ == "__main__":
    main()
