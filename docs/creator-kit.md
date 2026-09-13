# imgAPI 创作者资料包

[仓库](https://github.com/shanyeai/imgapi-image-generation) · [官网 imgapi.vip](https://imgapi.vip/) · [接入文档](https://imgapi.vip/api-docs)

供技术博主、开发者社区和教程作者准备演示使用。这里提供可核对的代码入口与录制流程，尚未提供真实付费生成的成片、耗时或成功率测试。

## 可以直接引用的介绍

> imgAPI 提供 AI 生图 API。这份公开示例仓库包含 Node.js、Python 客户端和文生图与参考图场景请求，开发者可以先在无 Key、无网络的模式下预览参数，再配置 CardKey 进行真实调用。示例包含参考图上传、异步轮询和任务恢复，官网为 imgapi.vip。

English: imgAPI provides an image generation API with public Node.js and Python integration examples. Preview a request without a Key, then configure server-side credentials for a real generation. Examples cover reference images, polling and task recovery. Website: [imgapi.vip](https://imgapi.vip/).

仓库代码与文档采用 [MIT License](../LICENSE)，可称为“MIT 开源接入示例”。复用时按许可证保留声明；在线 API 的调用仍遵循服务规则与计费，不因示例开源而免费。

## 推荐的三个内容角度

| 角度 | 适合的读者 | 可演示的内容 |
| --- | --- | --- |
| 给已有应用接入图片生成 | 独立开发者、AI 应用开发者 | 从场景 JSON 到客户端调用，再取得图片 URL |
| 生图超时后怎样避免重复提交 | 后端开发者 | 保存任务 ID、用 `--query` 继续查同一任务 |
| 商品图 / 封面工具如何组织请求 | 电商工具、内容工具作者 | 修改提示词、参考图与比例；两种语言复用同一份 JSON |

可用标题：

- 《给应用接入图片生成：Node.js 与 Python 两种写法》
- 《生图任务超时以后，我为什么保留任务 ID》——只有亲自完成相关实验后才使用第一人称。
- 《一个 JSON 跑两种语言：imgAPI 商品图接入示例》

## 约 90 秒的演示提纲

| 时间 | 画面与操作 | 讲解重点 |
| --- | --- | --- |
| 0–15 秒 | 仓库首页与场景请求文件 | 它解决什么接入问题，使用什么语言 |
| 15–30 秒 | `node node/run.mjs --dry-run --request examples/product-photo.json` | 这一步只预览请求，没有生成图片 |
| 30–45 秒 | 打开 JSON，调整提示词或比例 | 无需修改客户端即可换场景 |
| 45–70 秒 | 自行授权并配置 Key 后执行真实调用；录制时隐藏凭据 | 记录任务 ID，等待真实结果；耗时按实际发生填写 |
| 70–80 秒 | 如确需演示恢复，使用刚取得的 ID 执行 `--query` | 查询已有任务不创建新任务 |
| 80–90 秒 | 展示实际图片与仓库入口 | 展示可见结果，注明所用模型与参数 |

没有进行真实生成时，演示在请求预览处结束。不要用其他模型或预制图片冒充该命令的结果。

## 发布前准备一份可复现证据

至少保留：仓库 commit、日期、模型、完整脱敏请求、是否使用参考图、实际耗时、最终状态与原始图片。若提到价格或积分，附当时的规则和真实消耗；不要从一次成功推导整体成功率。

需要对比不同模型时，使用相同提示词与参考图，标明分辨率和质量设置，并保留失败样本。质量判断说明自己的用途，例如“瓶口结构完整”“左侧留白便于加标题”。

## 可改写的介绍帖草稿

> 整理了一份 imgAPI 生图 API 对接示例：Node.js 和 Python 都可以用同一份 JSON 请求，先预览参数，再配置 Key 生成图片。里面还包括参考图上传、任务 ID 保存和中断后继续查询。想给商品图工具或内容工作台接入生图，可以从这里开始：
>
> [GitHub 仓库](https://github.com/shanyeai/imgapi-image-generation) · [imgAPI 官网](https://imgapi.vip/)

这段是介绍草稿，不包含“亲测稳定”“免费生图”等未验证声明。收到赞助、赠送积分或其他合作支持时，按实际情况说明。仓库不承诺合作费用、免费额度或宣传效果。

## 素材与合作入口

准备静态图文时，可展示[实际离线预览输出](request-preview.md)，或截取仓库快速开始。图注写明“请求预览，未生成图片”；不要把仓库横幅或请求 JSON 当作生图效果展示。下载结果的 macOS/Linux 与 PowerShell 命令见[快速开始](../README.md#快速开始)。

目前可引用的素材是仓库说明、运行命令和自己的真实演示。新的场景可通过 [场景请求](https://github.com/shanyeai/imgapi-image-generation/issues/new?template=example_request.yml) 提出，完成接入后可通过 [使用案例](https://github.com/shanyeai/imgapi-image-generation/issues/new?template=showcase.yml) 分享。私人合作条款与凭据不要发到公开 Issue。
