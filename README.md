# 热点选题助手 · TrendPick Agent

> 不是帮你找热点，是帮你判断哪个热点不能追。

品牌借势最常见的失败不是"没找到热点"，而是：追了一个已经过气的梗；追了一个和自己正在发酵的负面撞车的梗；在灾难刚过去的那一周发了欢快的内容；把"喝了不烧心"写成了功效宣称。AI 找热点、写创意本来就很强，但不装 skill 时，它会把热榜上最火的东西排在第一位，然后给你五条全是"建议追"的方案。

「热点选题助手」是一个 Agent Skill。它把借势变成一套判断流程：**先查自己 → 看大环境 → 把梗聚成簇看曲线 → 五维判断 → 追 / 等 / 跳过**，每条结论都能回到一个链接和一个日期。跳过清单和推荐卡一样认真写，因为用户最想追的，往往就在跳过清单里。

## 每条推荐回答四个问题

| 问题 | 怎么回答 |
|---|---|
| **为什么是这个梗** | 拆成结构、情绪、梗源三层：借结构和情绪，不碰梗源 |
| **为什么是现在** | 同一个梗的几十个变体聚成一簇，看逐日曲线：首次出现、峰值周、近 7 天 vs 前 7 天；剩余窗口减去上线周期 |
| **为什么是这个品牌** | 五维：受众重合、产品接得住、调性不冲突、窗口够、没被做烂。每一维写依据，不打分 |
| **哪里会翻车** | 品牌、竞品、品类、原料四组词的舆情；灾难、战争、民族情绪事件；功效暗示、IP 肖像、国家象征等黄线 |

## 两个真实案例（2026-10-28，数据截至 10-27）

| | 星巴克中国（国内） | 极石 ROX（中东 UAE + 沙特） |
|---|---|---|
| 数据 | 抖音、微博、B站、知乎热榜 6 周，21,677 条 | X 当地热门 + Wikipedia 年度事件页 + Bing News + KOX TikTok 视频检索 36 次 |
| 先查自己 | 「消费入座」负面发酵中；品类有"咖啡与骨质疏松"传闻；原料有"硫磺熏制桂花" | 品牌声量很小、无负面；**沙特用户 10/27 起抵制 TikTok** |
| 大环境 | 10/22 西藏 7.0 级地震；10/27 姆巴佩事件 | 美以—伊朗战争；沙特持续遭胡塞袭击 |
| 追 | 可可系 × 摩卡；冷空气已到货 × 热饮（禁"进店取暖"画面） | UAE 冬季露营季 × 对外放电；UAE 国庆 12/2 ×「在阿布扎比造」。沙特本窗口不走 TikTok |
| 跳过（节选） | 「不烧心」（已过峰 + 功效暗示）、「喝大水」、「纯过日子」、万圣节（来不及） | TikTok 抵制本身、"防弹 / 安全感"叙事、「沙特丝绸之路」（查证后是电商推广）、国旗日（来不及） |
| 评分（12 项） | 不装 skill 3 / 12 → 装 skill 12 / 12 | 不装 skill 5.5 / 11 → 装 skill 10.5 / 11 |

ROX 一列是盲测版本：另起一个 Agent，只给它 skill 和需求。

不装 skill 的 AI 给星巴克的第一推荐是「这杯喝了不烧心」。详见 [cases/](cases/) 和 [evals/README.md](evals/README.md)。

## 为什么不会被模型迭代取代

模型越强，创意写得越好，但它不知道：这个梗在热榜上是第几天了、峰值在哪一周；你的品牌这周有没有在挨骂；你们从定题到上线要几天；上次推荐的梗你们用了没有、效果如何。这些要靠真实数据和台账，模型本身给不出来。skill 管的是数据纪律和判断框架，模型越强，执行得越好。

## 安装

**最简单：直接对你的 Agent 说**

> 帮我安装这个 skill：https://github.com/isa-moon/trendpick-agent

Claude Code、Codex、Cursor 这类能运行命令的 Agent 会读这一页，按下面「给 Agent 的安装步骤」装好。

**也可以用命令行**（需要 Node.js）：

```bash
npx skills add isa-moon/trendpick-agent -g
```

**或者手动**：下载仓库，把 `skills/trendpick-agent/` 这个文件夹复制到 Agent 的 skills 目录。

装完重启 Agent（或新开一个会话）。升级时重复同样的步骤即可，台账和历次选题方案在 skill 目录之外，不会被覆盖。

### 给 Agent 的安装步骤

1. 要安装的只有仓库里的 `skills/trendpick-agent/` 文件夹，不是整个仓库
2. 目标目录按你所在的 Agent 选：Claude Code 是 `~/.claude/skills/`，Codex 是 `~/.codex/skills/`；其他 Agent 用它自己的用户级 skills 目录，不确定就问用户
3. 下载并复制（有 git 用 git，没有就用 curl）：
   ```bash
   tmp=$(mktemp -d)
   git clone --depth 1 https://github.com/isa-moon/trendpick-agent "$tmp/repo" \
     || (mkdir -p "$tmp/repo" && curl -fsSL https://github.com/isa-moon/trendpick-agent/archive/refs/heads/main.tar.gz | tar xz -C "$tmp/repo" --strip-components 1)
   mkdir -p ~/.claude/skills
   rm -rf ~/.claude/skills/trendpick-agent
   cp -R "$tmp/repo/skills/trendpick-agent" ~/.claude/skills/
   rm -rf "$tmp"
   ```
   只替换 `trendpick-agent` 这一个文件夹，不要动 skills 目录里的其他 skill
4. 检查 `~/.claude/skills/trendpick-agent/SKILL.md` 存在，告诉用户装在哪、要重启 Agent，以及可以怎么开始用（见下）
5. 不需要现在装蓝优选热点 MCP 或 KOX。第一次使用时 skill 会检查，缺了再提示

## 使用

装好后在对话里说：

- 「热点选题助手，帮星巴克看看这个月有什么热梗能借，下周上线」
- 「帮极石 ROX 出几个中东的借势选题，TikTok 为主」
- 「最近那个『不烧心』的梗我们能不能追？」
- 「每周一帮我看看有什么能追的热点」（定期监测，只报和上次相比的变化）

第一次使用时会问台账放在哪（默认 `~/Documents/选题台账/`，一个品牌一个文件）。每次的选题方案也存在这个目录里，文件名是 `<品牌>-<日期>-选题.md`。

## 对环境的要求

skill 本身只是一个文件夹，**不会自动安装下面的工具**。第一次用时它会检查环境，缺什么就告诉你怎么装；不装也能跑，只是结果会粗一些。

- **蓝优选热点话题 MCP**：从蓝优选 skill 市场安装 `hot-topics-data`，填自己的 `blueai-` Key（蓝优选工具箱通用），重启 Agent
- **KOX**：登录 KOX 平台（[maxlauncher.cn](https://maxlauncher.cn) / [maxlauncher.io](https://maxlauncher.io)），左侧导航栏「KOX SKILL」→「安装 KOX Skill」，复制命令粘贴给 Agent

| 能力 | 推荐 | 没有时 |
|---|---|---|
| 国内热榜 | 蓝优选热点话题 MCP（抖音、微博、B站、知乎，按天） | 网页检索热榜聚合页，或请用户提供截图；生命周期只能粗判 |
| 海外热点 | WebFetch：trends24.in（X 当地热门）、Wikipedia 年度事件页 | 请用户提供本地团队的观察 |
| 海外视频脉搏、达人 | KOX（蓝色光标内部工具）`search-video` | 不做视频脉搏，只给达人类型，不给具体名单 |
| 脚本 | Python 3.8+，只用标准库 | 按文档手工也能走完，但聚类会慢很多 |

## 文件

```
trendpick-agent/
├── skills/trendpick-agent/       ← 安装的只有这个文件夹
│   ├── SKILL.md                  主文件：定位、流程、硬规则、完成标准
│   ├── references/
│   │   ├── judgment.md           判断标准：先查自己、大环境、红黄线、生命周期、五维、追等跳过
│   │   ├── sources.md            数据来源与取数，含实测可用性和坑
│   │   ├── card-format.md        交付物格式：开头三行、推荐卡、跳过表、拍板、数据说明
│   │   └── ledger.md             选题台账：品牌档案、只追加、读回规则
│   └── scripts/
│       ├── trend_stage.py        热榜聚类、逐日曲线、生命周期初判、句式梗发现
│       └── video_pulse.py        海外视频脉搏：真命中过滤、按周发布分布、头部视频
├── cases/                        两个真实案例的交付物和聚类结果（原始热榜数据不随仓库发布）
└── evals/                        基线、装 skill 后的产出、评分表、触发正反例（不随 skill 安装）
```

## 协议

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.zh-hans)：可以自由使用、修改和分享，但须署名，且不得用于商业目的。
