# 具身产业库｜Schema 设计 V0.1

> 草案，2026-09-18。
> 上游技术维度承接自 [ImChong/Robotics_Notebooks](https://github.com/ImChong/Robotics_Notebooks)（MIT）。

---

## 一、这是什么

一个记录「哪些公司在用什么技术栈、什么时间做了什么事」的公开数据库。

只收集可核查的事实并按时间排列，不做推断、不打分、不排名。使用者自己判断谁选对了、谁更可能活下来。

### 什么让它和同类库不一样

**不是话题范围，是形态和用途。** 同类库有做得很好的（见下节），但重叠是应该的——同一条原始来源，他们取「发布了什么产品」给人读，本库取「这透露了哪条轴的取值」给机器查。三点区别：

**一，技术栈可对比、收敛可观测。** 受控词表把技术与商业选择压成固定轴，历史取值不删，于是同一条轴上所有主体的取值可以按时间铺开，分散度下降就是收敛。产品字段写成自由文本就做不到这件事，而它恰好是「技术收敛时谁选对了」这个问题的答案所在。

**二，商业信号。** 招投标（谁在买、多少钱）、部署交付、公开定价、招聘信号、交付形态、目标场景。这一层同类库普遍不收。

**三，结构化与可核查。** 事件是机器可查的 YAML 而不是 markdown 表格，有 lint 门禁、编译视图和来源快照。链接会死，快照不会。

### 名录自建，不外包

`registry/orgs/` 是本库的骨架，**必须自己维护**，理由三条：

事件的 `orgs` 引用 registry，lint 校验主体必须存在。名录不全，事件无处可挂。

同类库的内容许可（CC BY-NC-SA）与本库不兼容，**法律上就不存在「靠别人维护名录」这个选项**。

更重要的是**别人的名录天生覆盖不到本库最需要的那几层**。租赁商、集成商、场景运营方不发论文、不办发布会，所以不会进以论文和产品为线索的知识库。而这批主体恰恰在「交付形态」和「目标场景」两条轴上信息量最大。名录的缺口要靠一手认知补，这件事没法外包。

### 相关工作

本库与以下两个库是互补关系，**单向引用，不复制内容**：

| 库 | 它做什么 | 本库的关系 |
|---|---|---|
| [ImChong/Robotics_Notebooks](https://github.com/ImChong/Robotics_Notebooks)（MIT） | 4000+ 页机器人技术知识库 | 技术轴取值指向它的页面，技术定义不在本库重建 |
| [RealXiaoze/humanoid-motion-intelligence](https://github.com/RealXiaoze/humanoid-motion-intelligence)（CC BY-NC-SA 4.0） | 公司与产品主表、公开信号时间线、数据集主表、求职信息 | 当**线索索引**（不是依赖）：顺着它标注的原始来源去抓一手页面、自存快照、按本库 schema 记录 |

「线索索引」和「依赖」的区别要紧：它停更、改范围或删库，本库照样能走，只是少一个发现新主体的渠道。骨架在自己手里。

⚠️ **humanoid-motion-intelligence 的内容许可是 CC BY-NC-SA 4.0**，与本库的 CC BY 4.0 不兼容（NC 禁商用、SA 要求衍生同权）。**不得把它的表格或编排导入本库**。事实本身不受版权保护，受保护的是选材与编排，所以必须回到原始来源取证。

### 边界

收录标准是一条成员规则，不是列举：**以通用机器人本体为最终载体的技术与商业主体**。

按这条线，人形本体、运控与小脑、VLA 模型、数据采集、仿真引擎、灵巧手与关节模组、系统集成、租赁运营都在里面；纯工业机械臂、AGV、无人机、扫地机在外面。遇到新公司按规则判，不逐个拍。

### 明确不做的事

- 不做推断、不打分、不排名
- 不收非公开或不可核查的信息
- 不做实时新闻流（这是可查询的结构化数据，不是资讯站）
- 不重建技术知识（技术页在 Robotics_Notebooks，本库只引用）
- 不做给人读的公司介绍页或产品评测（本库出的是结构化事实，阅读性编排交给同类库）
- 不导入其他库的表格或编排，只顺着它们的线索回到原始来源

> 主体名录、产品发布、融资这些**都收**——它们是轴取值和时间线的原料。
> 不重复的是「编排成文章给人读」那一层，不是话题本身。

---

## 二、四层数据模型

| 层 | 对象 | 性质 |
|---|---|---|
| 身份层 | `registry/orgs/`、`registry/datasets/` | 人工维护，**不可能从事件推导** |
| 事实层 | `events/` | 追加，不可变，唯一真源 |
| 视图层 | `build/` | 由身份层加事实层编译，可随时全量重建 |
| 词表层 | `vocab/` | 人工维护，变更需迁移 |

核心约束：**视图页上每一条事实都必须能回溯到具体事件**。写不出来源的内容不进库。

### 为什么需要单独的身份层

原设计是「主体页全部从事件编译」，写实现时撞墙了：名字、别名、成立年份、总部这些是主体的固有属性，事件流里推不出来。而 lint 要校验「事件引用的主体必须存在」，也得有个权威名单可查。

所以拆开：`registry/` 存身份、人工维护；`events/` 存事实、只追加；`build/` 是两者的编译产物，生成的文件一律不手改。

---

## 三、Event（事件）

事实层的唯一单位。一条事件一个文件，便于 git diff、PR 和逐条讨论。

路径：`events/<YYYY>/<MM>/<id>.yaml`

```yaml
id: evt-2026-09-10-unitree-g1-price-cut
date: 2026-09-10
date_precision: day          # day | month | quarter | year
type: pricing
orgs:
  - id: unitree
    role: subject            # subject | counterparty | investor | customer | supplier
title:
  zh: 宇树 G1 舞蹈款调价
  en: Unitree cuts G1 dance edition price
summary:
  zh: 官网标价从 X 调整为 Y。
  en: List price adjusted from X to Y.
axes:                        # 可选，本事件透露的技术栈或商业栈信息
  delivery_model: hardware-sale
evidence:
  - url: https://...
    publisher: 宇树官网
    tier: official           # official | primary | media | aggregator
    retrieved: 2026-09-18
    snapshot: snapshots/2026/09/unitree-g1-price-20260918.html
corroboration: single        # single | multi | conflicting
```

### 几个字段为什么这么设计

**`date_precision` 是必填的。** 产业信息大量只能精确到「2025 年下半年」。没有精度字段，就会被迫编一个具体日期，时间轴从此不可信。有了它，查询时可以按精度过滤。

**`tier` 描述的是来源类型，不是可信度。** official 是公司自己发布的，primary 是一手文件（招标公告、专利、SEC filing、工商登记），media 是媒体报道，aggregator 是二手聚合。这四类是客观属性，机器可判，不违反「不做推断」。

**`corroboration` 取代了可信度评分。** single 表示只有一个来源，multi 表示多个独立来源互相印证，conflicting 表示存在互相矛盾的来源。全部可机械判定。矛盾的来源全部保留，不替读者裁决。

**`orgs` 是数组且带 role。** 一条事件常涉及多方——A 投了 B、A 和 B 合作、C 中标了 D 的标。带 role 才能从任一方向检索。

### 事件类型

```
funding          融资、并购
corporate        成立、改名、注册变更、关停
product_launch   产品发布、版本迭代
deployment       落地部署、客户签约
procurement      招投标中标
partnership      合作、生态、联盟
personnel        关键人事
patent           专利
publication      论文、开源发布
hiring_signal    招聘信号
statement        官方表态
pricing          公开价格
```

`statement` 这一类单独存在，是为了承载「他们为什么选这条路线」。选型理由几乎不会有第三方客观记录，但公司自己会在发布会、技术博客、访谈里说。本库只记录「谁在什么时候这么说过」，信不信、后来打脸没有，读者自己看。

副作用是「说过什么」和「后来做了什么」自动落在同一条时间轴上。

---

## 四、视图层：Org 与 Dataset

两类对象，都不是手写的，都从事件流编译生成，都可随时全量重跑。

### Org（主体页）

agent 定期重新生成，人只维护事实和词表。

路径：`orgs/<id>.md`

```yaml
---
id: unitree
names:
  zh: 宇树科技
  en: Unitree Robotics
  aliases: [Unitree, 杭州宇树科技有限公司]
founded: 2016
hq: { country: CN, city: 杭州 }
status: active               # active | acquired | defunct | pivoted
layers: [embodiment, locomotion]
coverage: complete           # stub | draft | complete
event_count: 37
first_event: 2016-08
last_event: 2026-09-10
stack:
  sim_stack:
    - value: isaac-lab
      as_of: 2026-06
      evidence: [evt-2026-06-...]
    - value: mujoco
      as_of: 2024-03
      evidence: [evt-2024-03-...]
---
```

`stack` 里**历史取值不删**。一家公司从 MuJoCo 换到 Isaac Lab，两条都留着，各自带生效时间和来源事件。

这一条是整个库能观测「技术收敛」的基础：把所有主体在同一条轴上的取值按时间铺开，取值的分散度下降就是收敛，而且能看出哪条轴先收敛、哪条还在打。丢掉历史取值，这个能力就没了。

### Dataset（数据集页）

数据集值得单独立对象，因为它是数据战略唯一**硬邦邦可核查**的产物：规模、模态、机型、许可、发布时间全部写在发布页上，跨主体直接可比。而且一个数据集常被多方引用——采集方、发布方、赞助方、使用方可以是四家不同的公司。

路径：`datasets/<id>.md`

```yaml
---
id: agibot-world
names:
  zh: AgiBot World
  en: AgiBot World
publisher: agibot            # 发布主体
contributors: [gov-center-sh]
released: 2025-01
scale:
  episodes: 1000000
  hours: 
  robots: [agibot-a2]
modality: [rgbd, joint-trajectory, language-annotated]
acquisition: [teleop, real-robot]
license: cc-by-nc-4.0
openness: fully-open
coverage: draft
evidence: [evt-2025-01-...]
---
```

`scale` 字段全部可留空——很多数据集只公布其中一两项。留空好过填估算值。

---

## 五、Vocab（受控词表）

技术栈必须是受控词表，不能是自由文本。自由文本能存信息，但**无法横向对比**，而可对比性是本库唯一比新闻聚合强的地方。

一套产业层（主体在产业里的位置）加三组轴（技术、数据、商业）。

**取值的唯一真源在 [`vocab/`](vocab/)**，本节只讲结构，不重复列举，避免两处打架。

| 文件 | 内容 | 轴数 |
|---|---|---|
| [`vocab/layers.yaml`](vocab/layers.yaml) | 产业层，一个主体可占多层 | 9 个取值 |
| [`vocab/axes-tech.yaml`](vocab/axes-tech.yaml) | 运控路线、模型形态、仿真栈、本体形态 | 4 条 |
| [`vocab/axes-data.yaml`](vocab/axes-data.yaml) | 采集方式、数据模态、组织方式、开放程度 | 4 条 |
| [`vocab/axes-business.yaml`](vocab/axes-business.yaml) | 本体策略、交付形态、目标场景 | 3 条 |

技术轴每个取值带 `ref` 指向 Robotics_Notebooks 的页面路径，技术定义在上游，本库不复制。数据轴和商业轴每条带 `evidence_hint`，写明这条轴该去哪类来源核查。

**三组轴的分工就是「学术 + 商业结合」的落点。** 技术轴指向上游知识库，数据轴和商业轴是本库原创，三者挂在同一个主体上，于是「技术选择」和「商业结果」第一次能放在一起看。

### 为什么数据单独成组

**技术收敛之后，剩下的分野就是数据。** 本库的核心用途是观测收敛，那数据这条线就不能只是技术轴下的一个字段。

它还有个结构特点：数据**既是一个产业层，又是每家公司都有的一条战略轴**。既有纯做数采、标注、合成的公司，也有本体厂商自己建数据工厂、开放数据集。所以设计上两处都要有——`layers` 里有 `data` 这一层收纯做数据的主体，同时四条数据轴挂在**每一个**主体上，不管它是不是数据公司。

词表草案需要按真实产业分野调整，不照搬教科书分类。轴定错后面几百个条目都要返工，所以这是动工前必须先锁的东西。

---

## 六、目录结构

```
registry/orgs/*.yaml         身份层，人工维护
registry/datasets/*.yaml     身份层，人工维护
events/<YYYY>/<MM>/*.yaml    事实层，只追加
vocab/*.yaml                 受控词表
snapshots/<YYYY>/<MM>/       来源页面快照
scripts/                     lint / compile / ingest
tests/fixtures/              合规夹具，验证编译器
tests/fixtures-bad/          违规夹具，验证门禁真的会开火
build/                       编译产物，勿手改，不进 git
docs/                        站点
DESIGN.md                    本文档
```

---

## 七、四个操作

对齐 Robotics_Notebooks 的 ops 思路：LLM 是维护者，人是策展人。

**Ingest** — 从数据源产出事件。人只审来源和词表取值。

**Compile** — 事件流重新编译出主体页。幂等，可随时全量重跑。

**Lint** — 公开前的门禁，见下节。

**Publish** — 导出、索引、建站。

---

## 八、Lint 门禁

不满足的不进公开索引。

1. 每条事件至少一条 evidence，且 `url` + `retrieved` + `snapshot` 齐全
2. `date` 与 `date_precision` 自洽
3. `orgs` 引用的主体必须存在，不允许孤立引用
4. `axes` 取值必须命中词表，**拒绝自由文本**
5. 主体进公开索引需 ≥3 条带来源事件
6. 正文巡检推断性措辞（「我认为」「预计」「可能是因为」「有望」），命中即拒

第 4 条保证可比性，第 6 条把「中立」从口号变成机器强制执行的规则。

### 公开门槛按可核查密度，不按篇幅

一个只有三行的条目，只要每行都有日期和来源链接，它就是有用的。一篇写得很长但没出处的，是垃圾。

这条直接决定了一开始就公开是否成立——批量建的 stub 只要每条都带源，就不丢人。

---

## 九、来源与采集

| 类型 | 国内 | 海外 |
|---|---|---|
| 政府采购 / 招投标 | 中国政府采购网及各地平台 | USAspending.gov、SAM.gov、EU TED |
| 融资与工商 | 企查查、IT桔子 | Crunchbase、SEC EDGAR |
| 招聘 | BOSS、拉勾 | LinkedIn |
| 专利 | 国知局 | USPTO、EPO |
| 论文与开源 | Robotics_Notebooks 已有管道 | 同左 |
| 官方发布 | 官网 diff 监控、公众号 | 官网 diff 监控、博客 |

两个被低估的源：

**招投标直接给出客户和金额。** 这是非上市公司唯一稳定可得的「谁在买、多少钱」，比融资通稿实在。而且中美欧都有公开平台，是少数几个全球通用的高信号源。

**招聘 JD 是技术栈探针。** 招「熟悉 Isaac Lab」的工程师，仿真栈就不用猜。JD 公开、结构化、更新频繁、带时间戳，而且扩招某个方向往往比发布会早半年。

### 数据层专属的三个源

数据战略在公开信息里的痕迹比想象中重，而且这三处基本没人系统地收。

**数采员招聘直接暴露产能。** 一家公司同时招 50 个数据采集员，说明它在自建数据工厂而不是外包；岗位描述里的遥操设备、动捕棚、场景要求，又反过来透露采集方式。这是判断 `data_sourcing` 和 `data_acquisition` 最实在的依据，比通稿可靠。

**训练场与数据采集服务的招投标。** 国内政府和国资共建的具身训练场、数据集基地是这两年的独特现象，建设和运营全部走公开招标，金额、场景、承建方、验收指标都在公告里。这类项目同时暴露「谁在出钱」和「谁在承接」。

**数据集发布页本身。** 规模、模态、机型、许可写得清清楚楚，是全球通用且零成本的源。发布节奏也有信息量——连续发版说明数据闭环在转，发一次就停说明是宣发动作。

### 快照是硬要求

链接会死、通稿会改、官网会悄悄改参数。没有快照，两年后整个库就是一堆无法验证的断言。每条 evidence 落一份本地快照或 archive.org 存档。

---

## 十、双语

**结构化字段共用一套，只有摘要和简介分 `zh` / `en`。**

本库内容是结构化事实——日期、主体、事件类型、轴取值、来源链接——这些本身与语言无关。真正要翻的只有每条事件那一句摘要。这让双语从「两倍工作量」降到「多一个字段」，和长知识页的情况完全不同。

**站点默认中文。** `en` 字段照填，但不为了凑英文站拖慢入库节奏——英文展示层可以后补，数据结构已经预留好。

未定：主体页正文是否双语全译。

---

## 十一、冷启动

全球全覆盖，最容易死在铺不完、长期停在半成品。

1. 先锁词表
2. 用公开名录批量 bootstrap 建 stub，只填 names / hq / layers，coverage 标 stub
3. 先接一条管道（建议招投标或招聘 JD）跑通全链路，验证 schema 撑得住
4. 再逐条接入其余数据源

Robotics_Notebooks 里有批量建实体的脚本先例（`bootstrap_loco_manip_161_entities.py`、`ingest_china_opensource_panorama.py`），可以照抄模式。

### 实体消歧

全球 + 多源采集会立刻撞上同一主体多名字的问题：宇树 / Unitree / 杭州宇树科技有限公司，以及改名、子公司、中英文名。

Robotics_Notebooks 已有 `page-aliases.json` 和 `institutions.json` 两套机制，直接复用，不自己设计。

---

## 十二、与 Robotics_Notebooks 的关系

**单向引用，不 fork，不合并。**

技术轴的取值链到他的页面 URL。他的库越厚，本库的技术维度越有支撑，这个关系不需要他配合。

MIT 允许复用他的 `schema/` 和 `scripts/`，但要求保留版权声明（Copyright 2026 Chong Liu）。除法律最低限度外，README 显著位置写明技术维度承接自 Robotics_Notebooks 并链过去。

---

## 十三、待定项

1. **词表取值** — V0.1 草案已落 [`vocab/`](vocab/)，待按真实产业分野过一遍
2. 主体页正文是否双语全译
3. 事件 ID 命名规则的最终形式
4. 首条打通的采集管道选哪个
5. 仓库 slug（`具身产业库` 的英文标识，建议 `embodied-industry-db`）

## 已定

- 项目名：具身产业库
- 覆盖：全球，同一套标准
- 公开时机：一开始就公开，边建边攻
- 站点默认语言：中文
