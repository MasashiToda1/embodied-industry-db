# 受控词表

本目录定义具身产业库所有可枚举字段的取值。**取值必须命中词表，lint 拒绝自由文本。**

| 文件 | 内容 |
|---|---|
| `layers.yaml` | 产业层，主体在产业里的位置 |
| `axes-tech.yaml` | 技术轴，取值指向 Robotics_Notebooks |
| `axes-data.yaml` | 数据轴 |
| `axes-business.yaml` | 商业轴 |

## 字段约定

每个取值包含：

- `id` — 机器可读标识，小写连字符，进 lint 校验的就是它
- `zh` / `en` — 双语显示名
- `note` — 一句话说明「什么情况算这个取值」，给 ingest 时判断用，不是词典定义
- `ref` — 仅技术轴有，指向 Robotics_Notebooks 的页面路径

## `ref` 怎么解析

`ref` 存仓库相对路径，不存完整 URL，便于上游改站点结构时只改一处。

拼接基址：

- 仓库：`https://github.com/ImChong/Robotics_Notebooks/blob/main/`
- 站点：`https://imchong.github.io/Robotics_Notebooks/`

`ref` 为空表示上游暂无对应页面，本库不自建技术页，留空即可。

## 改词表的规矩

**加取值随时可以，改或删取值要做迁移。** 已有事件和视图页引用了旧 id，改动前先跑一遍引用检查，否则 lint 会大面积报错。

取值要按真实产业分野定，不照搬教科书分类。宁可粗一点、每个取值都有真实主体落进去，也不要造一堆空桶。
