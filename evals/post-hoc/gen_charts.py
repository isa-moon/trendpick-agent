# -*- coding: utf-8 -*-
"""事后验证图表：用蓝优选热榜真实数据（2026-10-28 ~ 11-10）生成 SVG。"""
import json, collections, datetime

import sys
# 用法：python3 gen_charts.py <热榜 JSON>
# JSON 来自蓝优选热点话题 MCP query_hot_topics_v2(start_time="2026-10-28", end_time="2026-11-10")，原始数据不随仓库发布
SRC = sys.argv[1] if len(sys.argv) > 1 else sys.exit("用法：python3 gen_charts.py <热榜 JSON>")
d = json.load(open(SRC))["data"]

days = [str(datetime.date(2026,10,28) + datetime.timedelta(days=i)) for i in range(14)]

def series(rx):
    import re
    p = re.compile(rx)
    c = collections.Counter(x["hottopic_time"][:10] for x in d if p.search(x["hottopic_title"]))
    return [c.get(k, 0) for k in days]

SETS = [
    ("「不烧心」句式", r"烧心", "判定：已过峰，不追 → ✅ 成立（后 7 天继续衰减）", "#2563eb"),
    ("「立冬」节点", r"立冬", "判定：节点按日期排期，不看曲线 → ✅ 成立（11/7 单日峰值 10 条）", "#059669"),
    ("「大结果」句式", r"大结果", "判定：正在爆发、11/4 前必须上线 → ❌ 判错（平尾，无常驻识别）", "#dc2626"),
]

W, H = 1060, 470
PAD_L, PAD_R, PAD_T, PAD_B = 64, 300, 56, 64
pw, ph = W-PAD_L-PAD_R, H-PAD_T-PAD_B
mx = 11
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<rect width="100%" height="100%" fill="#ffffff"/>',
       f'<text x="{PAD_L}" y="30" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="17" font-weight="600" fill="#111">事后验证：10 月底的判断 vs 11/10 的实际热榜</text>',
       f'<text x="{PAD_L}" y="48" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="12" fill="#6b7280">数据：蓝优选热点话题 MCP，抖音/微博/B站/知乎，2026-10-28 – 11-10，7,449 条</text>']

# 网格
for gv in range(0, mx+1, 2):
    y = PAD_T + ph - ph*gv/mx
    out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L+pw}" y2="{y:.1f}" stroke="#eef0f3" stroke-width="1"/>')
    out.append(f'<text x="{PAD_L-10}" y="{y+4:.1f}" text-anchor="end" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="10" fill="#9ca3af">{gv}</text>')

step = pw/(len(days)-1)
for i, dy in enumerate(days):
    x = PAD_L + i*step
    out.append(f'<text x="{x:.1f}" y="{PAD_T+ph+18}" text-anchor="middle" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="9" fill="#9ca3af">{dy[5:]}</text>')

# 11/7 立冬竖线
i7 = days.index("2026-11-07")
x7 = PAD_L + i7*step
out.append(f'<line x1="{x7:.1f}" y1="{PAD_T}" x2="{x7:.1f}" y2="{PAD_T+ph}" stroke="#059669" stroke-dasharray="3 3" stroke-width="1" opacity=".5"/>')
out.append(f'<text x="{x7:.1f}" y="{PAD_T-6}" text-anchor="middle" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="9" fill="#059669">立冬</text>')

for idx, (name, rx, verdict, color) in enumerate(SETS):
    s = series(rx)
    pts = " ".join(f"{PAD_L+i*step:.1f},{PAD_T+ph-ph*v/mx:.1f}" for i, v in enumerate(s))
    out.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>')
    for i, v in enumerate(s):
        if v:
            out.append(f'<circle cx="{PAD_L+i*step:.1f}" cy="{PAD_T+ph-ph*v/mx:.1f}" r="2.6" fill="{color}"/>')
    ly = PAD_T + 34 + idx*62
    lx = PAD_L + pw + 26
    out.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+18}" y2="{ly}" stroke="{color}" stroke-width="2.5"/>')
    out.append(f'<text x="{lx+26}" y="{ly+4}" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="13" font-weight="600" fill="#111">{name}</text>')
    # 折行
    words, line, lines = verdict, "", []
    for ch in words:
        line += ch
        if len(line) >= 24:
            lines.append(line); line = ""
    if line: lines.append(line)
    for j, ln in enumerate(lines):
        out.append(f'<text x="{lx}" y="{ly+20+j*15}" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="10.5" fill="#6b7280">{ln}</text>')

out.append(f'<text x="{PAD_L}" y="{H-16}" font-family="-apple-system,Helvetica,Arial,sans-serif" font-size="10" fill="#9ca3af">纵轴：当日热榜命中条目数（同一标题多平台可重复计）。生成于 2026-11-11，脚本见 evals/post-hoc/gen_charts.py</text>')
out.append('</svg>')
open("post-hoc.svg","w").write("\n".join(out))
print("wrote post-hoc.svg")
