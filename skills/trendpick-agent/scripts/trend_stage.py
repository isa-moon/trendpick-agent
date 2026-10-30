#!/usr/bin/env python3
"""热点选题助手 · TrendPick Agent — 热榜聚合与生命周期初判（仅标准库）。

把多天、多平台的热榜条目按话题聚合，算出：上榜天数、首次/末次上榜日、覆盖平台、
平台内最好排名、近 3 天 vs 之前的排名走势，并给出生命周期初判（萌芽/爆发/顶峰/衰退）。
初判只看数据，最终阶段由 agent 结合「品牌已蹭饱和度」等信号复核。

输入：hot-topics-data 导出的 xlsx，或其 JSON 返回（data 列表），或含同名列的 CSV。
用法：
  python3 trend_stage.py FILE [FILE ...] [--grep 关键词|关键词] [--top 80]
                         [--asof YYYY-MM-DD] [--min-days 1] [--json OUT.json]
  python3 trend_stage.py FILE [FILE ...] --cluster 名称=正则 [--cluster ...] [--show 8]
  python3 trend_stage.py FILE [FILE ...] --patterns [--middle] [--top 40]
  --grep  只保留标题含任一关键词的话题（| 分隔；正则里没有小写字母时区分大小写，NOVA 不会命中 Innovation）。单个标题寿命太短，不给阶段，只用来找线索
  --cluster  梗级聚类：热榜标题几乎每天都换写法，单标题很少在榜超过 2 天，
             所以判断一个梗的生命周期要把它的变体合成一簇看逐日曲线
  --show   每簇显示多少条代表条目（默认 8，0 = 全部），查误命中时调大
  --patterns 句式梗发现：找在多天、多个不同标题里反复出现的开头/结尾片段
             （如「…XX 刺客」「…XX 自由」），输出候选，交给 --cluster 复核
  --middle 和 --patterns 一起用：也统计标题中间的片段（「纯 X」「X 搭子」这类），噪音更多
  --asof  以哪一天为「今天」判断新旧；默认取数据里最晚的上榜日
"""
import argparse, csv, json, re, sys, zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, timedelta

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
PLATFORM_NAMES = {1: "抖音", 3: "B站", 5: "微博", 8: "知乎"}
PLATFORM_ALIASES = {"哔哩哔哩": "B站", "bilibili": "B站"}
FIELD_ALIASES = {
    "platform": ["平台", "platform"],
    "board": ["榜单名称", "board_name"],
    "title": ["热点标题", "hottopic_title"],
    "index": ["热度值", "hot_index"],
    "time": ["热点时间", "hottopic_time"],
    "url": ["热点链接", "hottopic_url"],
}


def read_xlsx(path):
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.findall(".//m:row", NS):
        cells = {}
        for c in row.findall("m:c", NS):
            col = re.match(r"[A-Z]+", c.get("r", "A")).group(0)
            v, t = c.find("m:v", NS), c.get("t")
            if t == "s":
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
            else:
                val = v.text if v is not None else ""
            cells[col] = val
        rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    keys = sorted(header, key=lambda k: (len(k), k))
    return [{header[k]: r.get(k, "") for k in keys} for r in rows[1:]]


def read_any(path):
    if path.endswith(".xlsx"):
        return read_xlsx(path)
    if path.endswith(".json"):
        data = json.load(open(path, encoding="utf-8"))
        return data.get("data", data) if isinstance(data, dict) else data
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pick(rec, field):
    for k in FIELD_ALIASES[field]:
        if k in rec and rec[k] not in (None, ""):
            return rec[k]
    return ""


def norm_title(t):
    # 合并同一话题的轻微写法差异：去空白、全角标点和 #
    return re.sub(r"[\s#＃“”\"'‘’：:，,。！!？?、·|｜【】\[\]（）()]", "", t).lower()


def compile_rx(rx):
    # 纯大写的拉丁词（品牌名缩写，如 NOVA）不区分大小写会误命中 Innovation，所以这种情况区分大小写
    bare = re.sub(r"\\.", "", rx)
    return re.compile(rx, 0 if re.search(r"[A-Z]", bare) and not re.search(r"[a-z]", bare) else re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--grep", default="")
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--asof", default="")
    ap.add_argument("--min-days", type=int, default=1)
    ap.add_argument("--json", default="")
    ap.add_argument("--cluster", action="append", default=[])
    ap.add_argument("--patterns", action="store_true")
    ap.add_argument("--middle", action="store_true")
    ap.add_argument("--show", type=int, default=8)
    a = ap.parse_args()

    recs = []
    for p in a.files:
        for r in read_any(p):
            title, ts = str(pick(r, "title")).strip(), str(pick(r, "time"))[:10]
            if not title or not re.match(r"\d{4}-\d{2}-\d{2}", ts):
                continue
            plat = pick(r, "platform")
            plat = PLATFORM_NAMES.get(int(plat), plat) if str(plat).isdigit() else str(plat)
            plat = PLATFORM_ALIASES.get(plat, plat)
            board = str(pick(r, "board"))
            if board and board not in ("总榜", "热搜榜", "热榜", "全站日榜"):
                plat = f"{plat}-{board}"
            try:
                idx = float(pick(r, "index") or 0)
            except ValueError:
                idx = 0.0
            recs.append({"title": title, "day": ts, "plat": plat, "idx": idx, "url": pick(r, "url")})
    if not recs:
        sys.exit("没有读到有效条目：检查文件格式或列名")

    # 平台内当日排名（热度值跨平台不可比，只在同平台同日内排序）
    by_pd = defaultdict(dict)
    for r in recs:
        cur = by_pd[(r["plat"], r["day"])]
        if r["idx"] > cur.get(r["title"], -1):
            cur[r["title"]] = r["idx"]
    rank = {}
    for (plat, day), m in by_pd.items():
        for i, (t, _) in enumerate(sorted(m.items(), key=lambda x: -x[1]), 1):
            rank[(plat, day, t)] = (i, len(m))

    asof = date.fromisoformat(a.asof) if a.asof else max(date.fromisoformat(r["day"]) for r in recs)

    if a.cluster:
        return run_clusters(a, recs, rank, asof)
    if a.patterns:
        return run_patterns(a, recs, asof)

    topics = defaultdict(lambda: {"titles": set(), "days": set(), "plats": set(), "best": {}, "url": ""})
    for r in recs:
        k = norm_title(r["title"])
        t = topics[k]
        t["titles"].add(r["title"])
        t["days"].add(r["day"])
        t["plats"].add(r["plat"])
        t["url"] = t["url"] or r["url"]
        rk, _ = rank[(r["plat"], r["day"], r["title"])]
        t["best"][r["plat"]] = min(t["best"].get(r["plat"], 9999), rk)

    pat = compile_rx(a.grep) if a.grep else None
    out = []
    for k, t in topics.items():
        title = max(t["titles"], key=len)
        if pat and not pat.search(" ".join(t["titles"])):
            continue
        days = sorted(t["days"])
        if len(days) < a.min_days:
            continue
        idle = (asof - date.fromisoformat(days[-1])).days

        out.append({
            "title": title,
            "days_on": len(days),
            "first": days[0],
            "last": days[-1],
            "idle_days": idle,
            "platforms": sorted(t["plats"]),
            "best_rank": t["best"],
            "url": t["url"],
        })

    # 排序：跨平台数 > 上榜天数 > 最好排名
    out.sort(key=lambda x: (-len(x["platforms"]), -x["days_on"], min(x["best_rank"].values())))
    out = out[: a.top]

    if a.json:
        json.dump({"asof": str(asof), "topics": out}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"# 数据截至 {asof}｜条目 {len(recs)}｜话题 {len(topics)}｜输出 {len(out)}")
    print("# 单个标题寿命很短，这里不判阶段；找到线索后用 --cluster 看簇的曲线")
    print("天数\t首次\t末次\t平台(最好名次)\t标题")
    for x in out:
        plats = " ".join(f"{p}#{r}" for p, r in sorted(x["best_rank"].items(), key=lambda kv: kv[1]))
        print(f"{x['days_on']}\t{x['first'][5:]}\t{x['last'][5:]}\t{plats}\t{x['title']}")


def cluster_stage(daily, asof):
    """daily: {day: 条目数}。按簇的逐日曲线初判阶段。"""
    days = sorted(daily)
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    idle = (asof - last).days

    def window(lo, hi):  # 含两端，距 asof 的天数
        return sum(n for d, n in daily.items() if lo <= (asof - date.fromisoformat(d)).days <= hi)

    recent, prev = window(0, 6), window(7, 13)
    # 历史峰值周：只比近两周会漏掉"两周前一波冲高、之后两周都很低"的梗（例：某梗两周前一天 4 条，之后零星）
    span = (asof - first).days
    peak = max(window(k, k + 6) for k in range(0, span + 1))
    if idle >= 7:
        return "衰退", idle
    if sum(daily.values()) < 5:
        return "样本不足", idle
    if span <= 6:
        return "萌芽" if len(days) <= 2 else "爆发", idle
    if recent > prev * 1.3 and recent >= peak * 0.5:
        return "爆发", idle
    if recent < peak * 0.4:
        return "衰退", idle
    if recent >= prev * 0.7:
        return "顶峰", idle
    return "衰退", idle


def run_clusters(a, recs, rank, asof):
    report = []
    print("# 阶段只对梗有意义。品牌、竞品、新闻簇只看近 7 天有没有、几条、名次多少，不看阶段")
    for spec in a.cluster:
        name, _, rx = spec.partition("=")
        pat = compile_rx(rx or name)
        hits = [r for r in recs if pat.search(r["title"])]
        if not hits:
            print(f"\n## {name}：0 条命中（{rx}）")
            print("如果这是节点（节日、节气、大促），热榜上还没出现是正常的：按日期排期，不看曲线（judgment.md §3）")
            report.append({"cluster": name, "hits": 0})
            continue
        daily, plats, best = defaultdict(int), defaultdict(int), {}
        seen = set()
        for r in hits:
            key = (r["plat"], r["day"], r["title"])
            if key in seen:
                continue
            seen.add(key)
            daily[r["day"]] += 1
            plats[r["plat"]] += 1
            rk, _ = rank[key]
            if r["title"] not in best or rk < best[r["title"]][0]:
                best[r["title"]] = (rk, r["plat"], r["day"], r["url"])
        stage, idle = cluster_stage(daily, asof)
        days = sorted(daily)
        print(f"\n## {name}｜初判：{stage}｜{len(seen)} 条 / {len(days)} 天｜{days[0]} → {days[-1]}（距今 {idle} 天）")
        weeks = [sum(n for d, n in daily.items() if k * 7 <= (asof - date.fromisoformat(d)).days < k * 7 + 7)
                 for k in range((asof - date.fromisoformat(days[0])).days // 7 + 1)]
        print("逐周（W0 = 最近 7 天）：" + " ".join(f"W{k}:{n}" for k, n in enumerate(weeks)))
        # 常驻：每周都有、量不小、没有峰，而且最近两周没有在涨（慢热的新梗会在涨）
        med = sorted(weeks)[len(weeks) // 2]
        steady = (len(weeks) >= 5 and min(weeks) > 0 and med >= 2 and sum(weeks) >= 10
                  and max(weeks) <= min(8, 2 * med)
                  and sum(weeks[:2]) / 2 <= 1.5 * sum(weeks[2:]) / len(weeks[2:]))
        if len(seen) < 10:
            print(f"⚠ 只有 {len(seen)} 条：阶段对一两条的增减很敏感，剔除误命中后重跑，并逐条看代表条目")
        if steady:
            print("⚠ 连续 5 周以上每周都有、没有明显的峰：可能是常驻说法，不是热梗（judgment.md §3）")
        print("平台：" + " ".join(f"{p}×{n}" for p, n in sorted(plats.items(), key=lambda x: -x[1])))
        # 逐日曲线（按周分行，便于肉眼看起落）
        d, line = date.fromisoformat(days[0]), []
        while d <= asof:
            line.append(f"{d.strftime('%m%d')}:{daily.get(str(d), 0)}")
            d += timedelta(days=1)
        for i in range(0, len(line), 7):
            print("  " + " ".join(line[i:i + 7]))
        print("代表条目（平台内最好名次）：")
        shown = sorted(best.items(), key=lambda x: x[1][0])
        for t, (rk, p, dy, u) in (shown[: a.show] if a.show else shown):
            print(f"  {p}#{rk} {dy[5:]} {t}")
        if a.show and len(shown) > a.show:
            print(f"  …另有 {len(shown) - a.show} 条，用 --show 0 看全部")
        report.append({"cluster": name, "regex": rx, "stage": stage, "hits": len(seen),
                       "days_on": len(days), "first": days[0], "last": days[-1], "idle_days": idle,
                       "platforms": dict(plats), "daily": dict(daily), "weekly": weeks, "steady": steady,
                       "examples": [{"title": t, "platform": p, "rank": rk, "day": dy, "url": u}
                                    for t, (rk, p, dy, u) in shown]})
    if a.json:
        json.dump({"asof": str(asof), "clusters": report}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run_patterns(a, recs, asof):
    """统计标题开头/结尾的 2–6 字片段：出现在 ≥3 天、≥4 个不同标题里的，是句式梗候选。"""
    titles = {}
    for r in recs:
        t = re.sub(r"[\s#＃！!？?。…~～：:，,、【】\[\]（）()“”\"]+$", "", r["title"])
        titles.setdefault(t, set()).add(r["day"])
    stat = defaultdict(lambda: {"titles": set(), "days": set()})
    for t, ds in titles.items():
        if len(t) < 5:
            continue
        for n in range(2, 7):
            if len(t) > n + 2:
                frags = {("尾", t[-n:]), ("头", t[:n])}
                if a.middle and n <= 4:
                    frags |= {("中", t[i:i + n]) for i in range(1, len(t) - n)}
                for frag in frags:
                    s = stat[frag]
                    s["titles"].add(t)
                    s["days"].update(ds)
    cands = [(k, v) for k, v in stat.items()
             if len(v["days"]) >= 3 and len(v["titles"]) >= 4 and not re.fullmatch(r"[\d\W_a-zA-Z]{1,3}", k[1])]
    # 爆发度：最集中的 14 天里的标题数 / 总标题数。新闻套话（如何评价/回应/道歉）全程均匀出现，
    # 梗会在一段时间内集中爆发，然后消失
    for k, v in cands:
        tdays = sorted(min(titles[t]) for t in v["titles"])
        best = 0
        for i, d0 in enumerate(tdays):
            end = str(date.fromisoformat(d0) + timedelta(days=13))
            best = max(best, sum(1 for d in tdays[i:] if d <= end))
        v["burst"], v["peak_n"] = best / len(tdays), best
    cands = [(k, v) for k, v in cands if v["burst"] >= 0.6 and v["peak_n"] >= 4]
    # 同一片段的更长版本如果覆盖了几乎同样的标题，只保留更长的（更具体）
    cands.sort(key=lambda kv: (-len(kv[1]["titles"]), -len(kv[0][1])))
    kept = []
    for (pos, frag), v in cands:
        if any(p == pos and (frag in f) and len(v["titles"] - kv["titles"]) <= 1 for (p, f), kv in kept):
            continue
        kept = [((p, f), kv) for (p, f), kv in kept
                if not (p == pos and f in frag and len(kv["titles"] - v["titles"]) <= 1)]
        kept.append(((pos, frag), v))
    kept.sort(key=lambda kv: (-kv[1]["peak_n"], -kv[1]["burst"]))
    print(f"# 句式候选（≥3 天、≥4 个标题、14 天爆发度 ≥60%）｜数据截至 {asof}｜前 {a.top} 个")
    print("位置\t片段\t峰值14天\t爆发度\t首次\t末次\t示例")
    for (pos, frag), v in kept[: a.top]:
        ds = sorted(v["days"])
        ex = "｜".join(sorted(v["titles"], key=len)[:3])
        print(f"{pos}\t{frag}\t{v['peak_n']}\t{v['burst']:.0%}\t{ds[0][5:]}\t{ds[-1][5:]}\t{ex}")
    print("\n提示：候选里仍会有剧名、人名、赛事名（它们也会集中爆发），按 judgment.md §2 分类后只对梗类片段跑 --cluster。")


if __name__ == "__main__":
    main()
