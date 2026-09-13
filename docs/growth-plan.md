# 仓库传播与开发者使用计划

目标：让有真实生图接入需求的开发者完成试用，并给教程作者提供可复现的介绍材料。以下是待执行的运营建议，不代表已获得曝光、用户或合作。

## 本轮解决的问题

| 原先的障碍 | 已准备的改进 | 怎么判断有效 |
| --- | --- | --- |
| 首次体验就需要 Key | 两种语言的 `--dry-run` | 新用户能否在没有凭据时看到请求结构 |
| 换用途要改脚本源码 | 共享场景 JSON | 能否只改 JSON 就运行自己的用例 |
| 只有中文说明 | 中英文 README | 英文读者能否完成配置、调用与恢复 |
| 很难判断是否维护 | 离线测试与 CI 配置 | 提交有可回看的测试结果 |
| 博主需要重新研究卖点 | 创作者资料包 | 能否按提纲自己复现，引用的事实能否核对 |
| 反馈没有结构 | Bug、场景请求、使用案例模板 | 是否出现可复现问题和实际应用案例 |

## 曝光入口

1. GitHub About 使用明确描述，Topics 只标实际提供的语言和能力：`imgapi`、`image-generation`、`image-generation-api`、`api-examples`、`nodejs`、`python`、`gpt-image-2`、`nano-banana`。
2. 官网 API 文档可在运行示例旁提供仓库链接；本轮未修改官网。链接文案说明“下载可运行的 Node.js / Python 示例”，避免只写 GitHub 图标。
3. 后续发布围绕一个具体问题写教程，例如“异步生图超时后恢复原任务”。教程链接到对应文档和 commit，而非只引导 Star。
4. 优先邀请做 AI 应用开发、独立开发、电商工具和自动化教程的作者。先看其是否真的演示代码与 API，再选择联系对象；暂不建立未经调查的博主名单。

GitHub Topics 为相关项目提供分类与发现入口；README 内容也可被仓库搜索检索。它们不保证排名或 Star 增长。依据：[Topics 官方说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)、[仓库搜索官方说明](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories)。

## 联系创作者前，还需要什么

优先补 2–3 个真实案例，每个包含输入 JSON、所用模型、参考图来源、原始结果、日期和可观察限制。至少一个案例完整展示“提交 → ID → 图片”，另一个展示恢复查询。当前场景 JSON 尚未完成真实付费效果测试。

已有真实案例后，可以把 [创作者资料包](creator-kit.md) 与固定版本链接一起交给作者，允许其独立评价。不要要求只展示成功结果，不承诺“稳定”“最快”“最低价”等未经验证的结论。赠送测试额度、付费合作、联系或发帖都应单独明确预算和对象。

GitHub 社交预览图可作为下一项素材：建议以真实演示画面为中心，突出 imgAPI、Node.js / Python、域名。官方建议尺寸 1280×640、文件小于 1 MB；需在仓库设置中上传，README 图片不等于已经设置社交预览。本轮未设置自定义预览图。依据：[GitHub 社交预览说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)。

## 看什么指标

| 阶段 | 可观察信号 | 限制 |
| --- | --- | --- |
| 发现 | GitHub 访问、克隆、引用来源 | 仅反映仓库访问；部分流量数据有可用范围限制 |
| 上手 | 使用反馈、可复现问题、首个成功案例 | 仓库没有遥测，不能自动统计每个人的 dry-run |
| 采用 | 外部项目、教程、真实集成案例 | Fork 或 Star 本身不证明 API 已被使用 |
| 服务使用 | 官网既有统计中的来源和后续使用 | 需要官网侧独立核对；本轮未接入跟踪或修改账户数据 |

发布后先看新用户卡在哪里，优先修补高频问题，再增加他们明确需要的框架示例。不为制造内容数量一次性堆叠多个未经验证的 SDK。

## 授权与状态

- 2026-09-13 更新：维护者已明确同意为本公开示例仓库添加 MIT 许可证，替代此前暂不添加许可证的决定。可称为“MIT 开源接入示例”，按许可证保留声明；在线 API 计费不受示例开源影响。
- 仓库内容与测试是本轮交付；真实生图案例、社交预览图、官网反向入口和对外联系是后续项。
- 本计划不创建后台监控、不发送消息、不购买推广、不自动消耗生图积分。

2026-09-12：仓库名称调整为 `imgapi-image-generation`，中英文首页使用品牌横幅与手机适配图，统一导航、运行环境和测试徽章；克隆命令、文档及反馈入口同步新名称。README 横幅不代表已设置 GitHub 社交预览图。

## 首页对照与 SEO 调整（2026-09-12）

用户明确优先搜索可发现性，其次是真实接入，介绍须简洁。Star 为本次 GitHub API 读取快照，不是效果归因。

| 参考仓库 | Star 快照 | 吸收的做法 |
| --- | ---: | --- |
| [Open WebUI](https://github.com/open-webui/open-webui) | 151,697 | 简介直接说明用途和支持范围，提供清楚的安装路径 |
| [Vercel AI SDK](https://github.com/vercel/ai) | 26,699 | 介绍之后进入安装与代码，按开发任务组织示例 |
| [Replicate Node.js](https://github.com/replicate/replicate-javascript) | 598 | 作为用途相近的 API 客户端参考，明确凭据与输入输出 |

本轮把横幅缩小，删除重复宣传句和首屏次要入口；将 Key 配置和真实调用提前，场景表直达 JSON。标题与正文自然包含 AI 生图 API、GPT Image 2、GPT Image 2.5、Nano Banana、Node.js、Python；补齐模型 ID 表和参考图请求示例。CLI、鉴权与计费行为保持原有契约。

GitHub 允许按名称、描述、README 内容、Topics 搜索仓库，依据：[官方仓库搜索说明](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories)。这次优化的是这些可控制的内容；GitHub 页面 meta、搜索引擎抓取与排名不由本仓库直接控制。不添加无效的 README meta 标签、关键词堆叠或虚假的部署入口，不把排版变化写成已获得 SEO 流量。

验收以桌面/手机真实渲染、两种语言导航、文案与链接检查、参考图 multipart 离线流程为准；付费出图、流量增长与搜索排名需要后续独立证据。此前创作者材料仍保留在文档层，主首页优先服务准备接入的开发者。
