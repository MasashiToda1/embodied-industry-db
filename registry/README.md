# 身份层

人工维护的主体与数据集身份。**这里的内容推导不出来**——名字、别名、成立年份、总部是固有属性，事件流里没有。

事实（谁在什么时候做了什么）一律进 `events/`，不要写到这里。

## 主体字段

```yaml
id: unitree                    # 小写连字符，与文件名一致
names:
  zh: 宇树科技                  # 必填
  en: Unitree Robotics
  aliases: [Unitree, 杭州宇树科技股份有限公司]
founded: 2016
hq: { country: CN, city: 杭州 }
status: active                 # 见 vocab/enums.yaml
layers: [embodiment, locomotion]   # 必填，见 vocab/layers.yaml
sources:                       # 填了 founded / hq 就该有来源
  - url: https://...
    tier: primary
    retrieved: 2026-09-18
    note: 工商登记信息
```

`aliases` 很重要。多源自动采集会撞上同一主体多个名字——宇树 / Unitree / 杭州宇树科技股份有限公司，还有改名和子公司。别名不全会导致同一家公司被建成两条。

## 为什么身份也要 sources

本库的规矩是每条事实可回溯。身份层不该例外：**「成立于 2016 年」和「2026 年发布了新机型」一样是可核查的断言**，只是它不带事件性质。

`founded` 或 `hq` 填了但没 `sources` 时，lint 会警告而不是报错——身份信息不阻塞入库，但会留在待补清单上。只填 `names` 和 `layers` 的条目不触发警告，因为那两项是自明的。
