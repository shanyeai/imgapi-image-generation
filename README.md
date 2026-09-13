<p>
<a href="https://imgapi.vip/"><picture>
  <source media="(max-width: 600px)" srcset="assets/readme-hero-mobile.svg">
  <img src="assets/readme-hero.svg" alt="imgAPI AI image generation API — Node.js / Python" width="1280">
</picture></a>
</p>

# imgAPI — AI 生图 API 示例

GPT Image 2、GPT Image 2.5、Nano Banana 的 **Node.js / Python 调用示例**，支持文生图、参考图生成和异步任务查询。

[获取 API Key](https://imgapi.vip/) · [API 文档与价格](https://imgapi.vip/api-docs) · [运行示例](#快速开始) · [English](README.en.md)

[![Offline tests](https://github.com/shanyeai/imgapi-image-generation/actions/workflows/test.yml/badge.svg)](https://github.com/shanyeai/imgapi-image-generation/actions/workflows/test.yml)

## 快速开始

需要 Node.js 22+ 或 Python 3.10+，任选一种。

```bash
git clone https://github.com/shanyeai/imgapi-image-generation.git
cd imgapi-image-generation
```

**1. 先预览请求**：任选一条运行，无需 Key、无需安装依赖，也不会提交生图任务。

```bash
node node/run.mjs --dry-run --request examples/quickstart.json
# 或 Python
python python/run.py --dry-run --request examples/quickstart.json
```

终端会输出 `"mode": "dry-run"`、`"network": false` 和请求参数。[查看完整输出及验证范围](docs/request-preview.md)。这一步便于检查提示词和模型参数，模型是否接受参数、能否生成图片仍需真实调用确认。

**2. 设置 Key**：准备真实调用时，在 [imgapi.vip](https://imgapi.vip/) 获取 CardKey，替换下面的占位符。脚本不会自动加载 `.env`；Key 只放在终端或服务端环境中。

```bash
# macOS / Linux
export IMGAPI_CARD_KEY='YOUR_16_HEX_CARD_KEY'
```

<details>
<summary>Windows PowerShell</summary>

```powershell
$env:IMGAPI_CARD_KEY = 'YOUR_16_HEX_CARD_KEY'
```

</details>

**3. 运行一次生图**：默认使用 GPT Image 2、1K、1:1，按服务规则消耗积分。

```bash
# Node.js：无需安装依赖
node node/run.mjs --request examples/quickstart.json
```

```bash
# Python
python -m pip install -r python/requirements.txt
python python/run.py --request examples/quickstart.json
```

成功后输出**任务 ID 和图片 URL**。异步任务 ID 保存到当前目录的 `task-id.txt`。

**4. 保存图片**：将下面的占位符替换为成功返回的完整图片 URL，保留其查询参数。选一个未使用的文件名；下载链接可能过期，取得结果后及时保存。下载不需要附带 CardKey。

```bash
# macOS / Linux：单引号保护 URL 中的 & 等字符
curl --fail --location --output result.png 'PASTE_RETURNED_IMAGE_URL_HERE'
```

<details>
<summary>Windows PowerShell</summary>

```powershell
Invoke-WebRequest -Uri 'PASTE_RETURNED_IMAGE_URL_HERE' -OutFile 'result.png'
```

</details>

`result.png` 只是示例文件名，下载命令不会转换图片格式；请按实际格式命名。不要公开带签名的下载链接。

## 选择场景

两种语言共用同一份 JSON。将上面的 `--request` 文件换成：

| 用途 | 请求文件 | 使用方式 |
| --- | --- | --- |
| 文生图 / Text to image | [quickstart.json](examples/quickstart.json) | 修改 `prompt` |
| 电商商品图 | [product-photo.json](examples/product-photo.json) | 修改商品描述 |
| 文章封面 | [article-cover.json](examples/article-cover.json) | 修改主题，保留标题留白 |
| 参考图 / Image to image | [reference-edit.json](examples/reference-edit.json) | 将自己的图片放到 `reference.png` |

[参数与参考图说明](examples/README.md)。这些是输入示例，尚未进行本批场景的付费效果实测。

## 支持的模型

| 模型 | JSON 的 `model` 值 |
| --- | --- |
| GPT Image 2 | `gpt-image-2` |
| GPT Image 2.5 | `gpt-image-2.5`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst` |
| Nano Banana 2 | `nano-banana-2` |
| Nano Banana Pro | `nano-banana-pro` |

在请求 JSON 中修改 `model`。当前可用性、参数组合与价格以 [imgAPI 文档](https://imgapi.vip/api-docs) 为准。

## 任务恢复与项目接入

等待中断后，用原 ID 继续查：`node node/run.mjs --query YOUR_TASK_ID`，或 `python python/run.py --query YOUR_TASK_ID`。提交结果不确定时先核对控制台，避免重复创建任务。

也可读取上次运行保存的任务 ID（文件只保留最近一次写入的 ID）：

```bash
# macOS / Linux；Python 可替换命令前半段
node node/run.mjs --query "$(cat task-id.txt)"
```

```powershell
# Windows PowerShell
node node/run.mjs --query (Get-Content -LiteralPath 'task-id.txt' -Raw).Trim()
```

已有应用可导入 [`createImgApiClient`](node/imgapi.mjs) 或 [`ImgApiClient`](python/imgapi.py)。完整写法见 [Node.js / Python 接入指南](docs/integration.md)。此接口使用自己的 JSON 协议，不能仅替换 OpenAI SDK 的 base URL。

[排错](docs/troubleshooting.md) · [反馈问题](https://github.com/shanyeai/imgapi-image-generation/issues) · [贡献与离线测试](CONTRIBUTING.md) · [教程作者资料](docs/creator-kit.md)

仓库暂未添加开源许可证；需要复用授权时请联系维护者。CI 只验证离线示例，不代表线上生成效果或可用率。
