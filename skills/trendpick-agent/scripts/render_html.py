#!/usr/bin/env python3
"""把选题方案 Markdown 转成固定样式的 HTML。只用标准库。

用法：
  python3 render_html.py <方案.md> [-o 输出.html]

不传 -o 时，输出到 Markdown 旁边的同名 .html。
样式来自 ../assets/report.css，原样内联进 HTML：一个文件，双击就能打开，
不联网、不跟随系统切换夜间模式。不管哪个模型写的 Markdown，
只要按 references/card-format.md 的格式，出来的 HTML 都长一个样。
"""
import argparse
import html
import re
import sys
from datetime import date
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "assets" / "report.css"

# ---------------------------------------------------------------- 行内

INLINE = re.compile(
    r"`([^`]+)`"                                 # 1 代码
    r"|\[([^\]]+)\]\((https?://[^)\s]+)\)"        # 2,3 链接
    r"|\*\*(.+?)\*\*"                            # 4 加粗
    r"|(https?://[^\s<>（）()「」，。；、|]+)"     # 5 裸链接
)

TAG_RULES = [  # 跳过表「类型」和标签着色
    ("red", re.compile(r"红线")),
    ("amber", re.compile(r"黄线|时机|衰退|过峰|来不及")),
    ("purple", re.compile(r"调性|冲突")),
    ("blue", re.compile(r"饱和|做烂|做过|占满")),
    ("orange", re.compile(r"竞品|IP|肖像|版权|原料|自身|舆情")),
]


def inline(s):
    out, pos = [], 0
    for m in INLINE.finditer(s):
        out.append(html.escape(s[pos:m.start()]))
        if m.group(1) is not None:
            out.append(f"<code>{html.escape(m.group(1))}</code>")
        elif m.group(2) is not None:
            out.append(f'<a href="{html.escape(m.group(3), quote=True)}" target="_blank" rel="noopener">'
                       f"{inline(m.group(2))}</a>")
        elif m.group(4) is not None:
            out.append(f"<strong>{inline(m.group(4))}</strong>")
        else:
            u = m.group(5)
            short = re.sub(r"^https?://(www\.)?", "", u)
            short = short if len(short) <= 42 else short[:40] + "…"
            out.append(f'<a class="url" href="{html.escape(u, quote=True)}" target="_blank" rel="noopener">'
                       f"{html.escape(short)}</a>")
        pos = m.end()
    out.append(html.escape(s[pos:]))
    return "".join(out)


def strip_md(s):
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"[*`#>]", "", s).strip()


# ---------------------------------------------------------------- 块级

def is_table_row(line):
    return line.strip().startswith("|") and line.strip().endswith("|")


def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip()[1:-1])
    return [c.strip().replace("\\|", "|") for c in cells]


def render_table(lines, kind=""):
    rows = [split_row(l) for l in lines if not re.fullmatch(r"\|[\s:|-]+\|", l.strip())]
    if not rows:
        return ""
    head, body = rows[0], rows[1:]
    type_col = next((i for i, h in enumerate(head) if strip_md(h) in ("类型", "原因类型")), None)
    h = ["<div class=\"table-wrap\"><table><thead><tr>"]
    h += [f"<th>{inline(c)}</th>" for c in head]
    h.append("</tr></thead><tbody>")
    for r in body:
        r = r + [""] * (len(head) - len(r))
        h.append("<tr>")
        for i, c in enumerate(r[: len(head)]):
            if i == type_col and c:
                h.append(f"<td>{tags(c)}</td>")
            else:
                h.append(f"<td>{inline(c)}</td>")
        h.append("</tr>")
    h.append("</tbody></table></div>")
    return "".join(h)


def tags(text):
    # 只在括号外按 + 、 ， 拆，「分类（新闻 / 政务）」保持一个标签
    parts, buf, depth = [], "", 0
    for ch in strip_md(text):
        depth += ch in "（("
        depth -= ch in "）)"
        if depth <= 0 and ch in "+＋、，,":
            parts.append(buf.strip()); buf = ""
        else:
            buf += ch
    parts = [p for p in parts + [buf.strip()] if p]
    out = []
    for p in parts:
        color = next((c for c, rx in TAG_RULES if rx.search(p)), "")
        out.append(f'<span class="tag {color}">{html.escape(p)}</span>')
    return "".join(out)


def render_blocks(lines):
    """通用 Markdown 块：段落、列表、表格、引用、代码、小标题。"""
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()
        if not s or re.fullmatch(r"-{3,}|\*{3,}", s):
            i += 1
            continue
        if s.startswith("```"):
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                j += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(lines[i + 1:j]))}</code></pre>")
            i = j + 1
            continue
        if is_table_row(s):
            j = i
            while j < n and is_table_row(lines[j]):
                j += 1
            out.append(render_table(lines[i:j]))
            i = j
            continue
        if s.startswith(">"):
            j = i
            buf = []
            while j < n and lines[j].strip().startswith(">"):
                buf.append(lines[j].strip()[1:].strip())
                j += 1
            out.append('<div class="callout">' + "".join(f"<p>{inline(b)}</p>" for b in buf if b) + "</div>")
            i = j
            continue
        m = re.match(r"(#{3,6})\s+(.*)", s)
        if m:
            lvl = min(len(m.group(1)) + 0, 4)
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        if re.match(r"([-*+]|\d+[.)、])\s+", s):
            j, html_list = render_list(lines, i)
            out.append(html_list)
            i = j
            continue
        buf = [s]
        j = i + 1
        while j < n and lines[j].strip() and not re.match(r"(#{1,6}\s|[-*+]\s|\d+[.)、]\s|\||>|```)", lines[j].strip()):
            buf.append(lines[j].strip())
            j += 1
        out.append(f"<p>{'<br>'.join(inline(b) for b in buf)}</p>")
        i = j
    return "\n".join(out)


def render_list(lines, i):
    first = lines[i].strip()
    ordered = bool(re.match(r"\d+[.)、]\s+", first))
    tag = "ol" if ordered else "ul"
    base = len(lines[i]) - len(lines[i].lstrip())
    items, j = [], i
    while j < len(lines):
        raw = lines[j]
        s = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if not s:
            break
        m = re.match(r"([-*+]|\d+[.)、])\s+(.*)", s)
        if m and indent <= base:
            items.append([m.group(2)])
        elif items and (indent > base or not m):
            items[-1].append(raw)
        else:
            break
        j += 1
    parts = [f"<{tag}>"]
    for it in items:
        head, rest = it[0], it[1:]
        sub = render_blocks([r[base + 2:] if len(r) > base + 2 else r.strip() for r in rest]) if rest else ""
        parts.append(f"<li>{inline(head)}{sub}</li>")
    parts.append(f"</{tag}>")
    return j, "".join(parts)


# ---------------------------------------------------------------- 结构识别

H2_KIND = [
    ("go", re.compile(r"推荐|【追】|^追$|追）")),
    ("watch", re.compile(r"观察|（等）|^等")),
    ("skip", re.compile(r"跳过")),
    ("defaults", re.compile(r"拍的板|默认")),
    ("data", re.compile(r"数据说明")),
    ("self", re.compile(r"先查自己|自查|大环境")),
    ("ledger", re.compile(r"台账")),
    ("appendix", re.compile(r"附录|过程记录|原始输出")),
]
COLLAPSED = {"ledger", "appendix"}
NAV_LABEL = {"go": "追", "watch": "等", "skip": "跳过", "defaults": "拍的板",
             "data": "数据说明", "self": "先查自己", "ledger": "台账", "appendix": "附录"}

FIELD_ALIASES = {
    "一句话": "一句话", "借的梗": "借的梗", "借的节点": "借的节点", "为什么是现在": "为什么是现在",
    "五维": "五维", "拆梗": "拆梗", "切入角度": "切入角度", "风险与规避": "风险与规避",
    "参考内容": "参考内容", "适合的达人类型": "达人类型", "达人类型": "达人类型",
}
FIELD_RX = re.compile(r"^\*\*(" + "|".join(map(re.escape, FIELD_ALIASES)) + r")\*\*[：:]\s*(.*)$")
LEVELS = [("冲突", "conflict"), ("强", "strong"), ("中", "mid"), ("弱", "weak")]


def level_class(word):
    for k, c in LEVELS:
        if word.startswith(k):
            return c
    return "other"


def render_dims(lines):
    rows = []
    for l in lines:
        m = re.match(r"\s*[-*]\s*(.+?)[：:]\s*(.+)$", l)
        if not m:
            continue
        name, rest = m.group(1), m.group(2)
        lvl, _, why = rest.partition("｜") if "｜" in rest else rest.partition("|")
        if not why:
            lvl, why = rest, ""
        lvl = lvl.strip()
        rows.append(f'<div class="dim"><span class="dim-name">{inline(name)}</span>'
                    f'<span class="lvl lvl-{level_class(strip_md(lvl))}">{inline(lvl)}</span>'
                    f'<span class="dim-why">{inline(why.strip())}</span></div>')
    return '<div class="dims">' + "".join(rows) + "</div>" if rows else render_blocks(lines)


ANGLE_KEYS = ("钩子", "露出", "风险")


def render_angles(lines):
    items = []
    for l in lines:
        m = re.match(r"\s*(\d+)[.)、]\s+(.*)", l)
        if m:
            items.append(m.group(2))
        elif items and l.strip():
            items[-1] += " " + l.strip()
    if not items:
        return render_blocks(lines)
    out = ['<div class="angles">']
    for k, text in enumerate(items, 1):
        segs = re.split(r"(?:。|；|\s)(?=(?:" + "|".join(ANGLE_KEYS) + r")[：:])", text)
        head, extra = segs[0], segs[1:]
        nm = re.match(r"(\*\*.+?\*\*|[^：:]{1,24})[：:]\s*(.*)", head)
        name, desc = (nm.group(1), nm.group(2)) if nm else ("", head)
        dl = "".join(f"<dt>{html.escape(e[:2])}</dt><dd>{inline(e[3:].strip().rstrip('。'))}</dd>"
                     for e in extra if e[:2] in ANGLE_KEYS)
        out.append(f'<div class="angle"><div class="angle-n">{k}</div><div>'
                   f'<p><span class="angle-name">{inline(strip_md(name))}</span></p>'
                   f'<p>{inline(desc)}</p>{f"<dl>{dl}</dl>" if dl else ""}</div></div>')
    out.append("</div>")
    return "".join(out)


def render_borrow(text):
    parts = [p.strip() for p in re.split(r"[｜|]", text) if p.strip()]
    if len(parts) < 2:
        return f"<p>{inline(text)}</p>"
    pills = "".join(f'<span class="pill {"green" if i == 0 else ""}">{inline(p)}</span>' for i, p in enumerate(parts[:1]))
    rest = "".join(f"<p>{inline(p)}</p>" for p in parts[1:])
    return f'<div class="pills">{pills}</div>{rest}'


def render_card(title, lines, kind):
    kind_cls = "watch" if kind == "watch" else ""
    badge = "等" if kind == "watch" else "追"
    title = re.sub(r"^【[追等]】\s*", "", title.strip())
    fields, pre, cur = [], [], None
    for l in lines:
        m = FIELD_RX.match(l.strip())
        if m:
            cur = [FIELD_ALIASES[m.group(1)], [m.group(2)] if m.group(2) else []]
            fields.append(cur)
        elif cur:
            cur[1].append(l)
        else:
            pre.append(l)
    lead, body = "", []
    for name, val in fields:
        text = "\n".join(val).strip()
        if name == "一句话":
            lead = f'<div class="lead">{inline(text)}</div>'
            continue
        if name == "五维":
            v = render_dims(val)
        elif name == "切入角度":
            v = render_angles(val)
        elif name in ("借的梗", "借的节点") and len(val) == 1:
            v = render_borrow(text)
        elif name == "风险与规避" and "｜" in text and len(val) == 1:
            v = "<ul>" + "".join(f"<li>{inline(p.strip())}</li>" for p in text.split("｜") if p.strip()) + "</ul>"
        else:
            v = render_blocks(val)
        body.append(f'<div class="field"><div class="k">{html.escape(name)}</div><div class="v">{v}</div></div>')
    extra = render_blocks(pre) if any(x.strip() for x in pre) else ""
    return (f'<article class="card {kind_cls}"><div class="card-head"><span class="badge">{badge}</span>'
            f"<h3>{inline(title)}</h3></div>{lead}{extra}{''.join(body)}</article>")


def classify_h2(title):
    t = strip_md(title)
    for k, rx in H2_KIND:
        if rx.search(t):
            return k
    return "other"


def clean_h2(title):
    t = re.sub(r"^[一二三四五六七八九十\d]+[、.．]\s*", "", strip_md(title))
    return re.sub(r"[（(][^）)]*judgment\.md[^）)]*[）)]", "", t).strip()


# ---------------------------------------------------------------- 开头

STAT_RX = re.compile(r"追\s*(\d+)\s*条?[^｜|等]*[｜|]\s*(?:观察|等)\s*(\d+)\s*条?[^｜|]*[｜|]\s*(?:建议)?跳过\s*(\d+)\s*条?(.*)")
FACT_KEYS = ["结论", "品牌自身", "大环境", "数据"]


def parse_top(lines):
    facts, rest = {}, []
    for l in lines:
        if l.strip().startswith("```"):
            continue  # 有的模型把开头几行包在代码块里，去掉围栏，内容照常识别
        s = l.strip()
        m = re.match(r"^[-*]?\s*\*{0,2}(结论|品牌自身|大环境|数据)\*{0,2}[：:]\s*(.+)$", s)
        if m and m.group(1) not in facts:
            facts[m.group(1)] = m.group(2).strip()
        else:
            rest.append(l)
    return facts, rest


def render_hero(title, facts, intro_lines, run_date):
    stats = ""
    m = STAT_RX.search(facts.get("结论", ""))
    if m:
        go, watch, skip, tail = m.groups()
        red = re.search(r"红线\s*(\d+)", tail)
        stats = ('<div class="stats">'
                 f'<div class="stat go"><div class="n">{go}</div><div class="l">追</div><div class="s">现在就做</div></div>'
                 f'<div class="stat watch"><div class="n">{watch}</div><div class="l">等</div><div class="s">等信号再定</div></div>'
                 f'<div class="stat skip"><div class="n">{skip}</div><div class="l">跳过</div>'
                 f'<div class="s">{f"其中红线 {red.group(1)} 条" if red else "看起来能追，其实不该追"}</div></div></div>')
    dl = "".join(f"<dt>{k}</dt><dd>{inline(facts[k])}</dd>" for k in FACT_KEYS if k in facts and k != "结论")
    if "结论" in facts and not stats:
        dl = f"<dt>结论</dt><dd>{inline(facts['结论'])}</dd>" + dl
    intro = render_blocks(intro_lines) if any(l.strip() for l in intro_lines) else ""
    return (f'<header class="hero"><div class="eyebrow">热点选题助手 · TrendPick Agent ｜ 选题方案</div>'
            f"<h1>{inline(title)}</h1><div class=\"meta\">方案日期 {run_date}</div>"
            f'{stats}<dl class="facts">{dl}</dl>{intro}</header>')


# ---------------------------------------------------------------- 主流程

def split_sections(lines):
    """按 # 和 ## 切。# 只认第一个（报告标题），后面的 # 当作 ## 处理（例如附录里的台账）。"""
    title, top, sections, cur = "", [], [], None
    in_code = False
    for l in lines:
        if l.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,2})\s+(.*)$", l)
        if m and m.group(1) == "#" and not title:
            title = m.group(2).strip()
            continue
        if m:
            cur = [m.group(2).strip(), []]
            sections.append(cur)
            continue
        (cur[1] if cur else top).append(l)
    return title, top, sections


def split_cards(lines):
    """在章节里找 ### 【追】/【等】 卡片，其余照常渲染。"""
    chunks, cur = [], ["", []]
    for l in lines:
        m = re.match(r"^###\s+(.*【[追等]】.*)$", l)
        if m:
            chunks.append(cur)
            cur = [m.group(1), []]
        else:
            cur[1].append(l)
    chunks.append(cur)
    return chunks


def render(md_text, src_name=""):
    lines = md_text.replace("\r\n", "\n").split("\n")
    title, top, sections = split_sections(lines)
    facts, intro = parse_top(top)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", src_name)  # 文件名 <品牌>-<YYYY-MM-DD>-选题.md
    run_date = m.group(1) if m else date.today().isoformat()

    nav, body = [], []
    # 顶层直接出现的【追】卡（有些交付物把卡片放在 ## 级别）
    for idx, (h2, sec_lines) in enumerate(sections):
        kind = classify_h2(h2)
        card_in_title = re.search(r"【([追等])】", h2)
        if card_in_title:
            kind = "go" if card_in_title.group(1) == "追" else "watch"
            body.append(f'<section class="sec sec-{kind}" id="s{idx}">'
                        + render_card(re.sub(r"^\d+[.．、]\s*", "", h2), sec_lines, kind) + "</section>")
            nav.append((f"s{idx}", "追" if kind == "go" else "等", kind))
            continue
        sid = f"s{idx}"
        inner = []
        for ctitle, clines in split_cards(sec_lines):
            if ctitle:
                ck = "watch" if "【等】" in ctitle else "go"
                inner.append(render_card(ctitle, clines, ck))
            elif any(x.strip() for x in clines):
                inner.append(render_blocks(clines))
        label = NAV_LABEL.get(kind) or clean_h2(h2)[:8]
        if kind in COLLAPSED:
            body.append(f'<details class="sec sec-{kind}" id="{sid}"><summary><h2>{inline(clean_h2(h2))}</h2></summary>'
                        f'{"".join(inner)}</details>')
        else:
            body.append(f'<section class="sec sec-{kind}" id="{sid}"><h2>{inline(clean_h2(h2))}</h2>{"".join(inner)}</section>')
        nav.append((sid, label, kind))

    seen, nav_html = set(), []
    for sid, label, kind in nav:
        if label in seen:
            continue
        seen.add(label)
        nav_html.append(f'<a class="{kind}" href="#{sid}">{html.escape(label)}</a>')

    css = CSS.read_text(encoding="utf-8")
    page_title = strip_md(title) or "选题方案"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light only">
<meta name="generator" content="trendpick-agent render_html.py">
<title>{html.escape(page_title)}</title>
<style>
{css}
</style>
</head>
<body>
<nav class="toc"><div class="in">{''.join(nav_html)}</div></nav>
<main class="wrap">
{render_hero(title or '选题方案', facts, intro, run_date)}
{chr(10).join(body)}
<footer>热点选题助手 · TrendPick Agent 生成 ｜ 判断以数据截至日期为准，上线前请再看一眼当日热搜</footer>
</main>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="把选题方案 Markdown 转成固定样式的 HTML")
    ap.add_argument("md", help="选题方案 Markdown 文件")
    ap.add_argument("-o", "--out", help="输出 HTML 路径，默认和 Markdown 同名")
    a = ap.parse_args()
    src = Path(a.md)
    if not src.is_file():
        sys.exit(f"找不到文件：{src}")
    if not CSS.is_file():
        sys.exit(f"找不到样式文件：{CSS}（skill 安装不完整，重新安装即可）")
    out = Path(a.out) if a.out else src.with_suffix(".html")
    out.write_text(render(src.read_text(encoding="utf-8"), src.name), encoding="utf-8")
    print(out.resolve())


if __name__ == "__main__":
    main()
