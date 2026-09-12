# imgAPI API 对接示例

**imgAPI** 的 AI 生图 API 接入代码，包含 Node.js 和 Python 示例，支持文字生图、参考图、异步查询和任务恢复。

- 官网：[imgAPI · imgapi.vip](https://imgapi.vip/)
- API 文档：[imgapi.vip/api-docs](https://imgapi.vip/api-docs)
- API Base URL：`https://imgapi.vip/prod-api`

## 快速开始

克隆仓库，在仓库根目录执行下面的命令：

```bash
git clone https://github.com/shanye1402-hash/imgapi-examples.git
cd imgapi-examples
```

在 imgAPI 官网获取 CardKey，然后设置终端或服务端环境变量。以下值是占位符，需替换为自己的 16 位十六进制 CardKey。

```powershell
# Windows PowerShell
$env:IMGAPI_CARD_KEY = 'YOUR_16_HEX_CARD_KEY'
```

```bash
# macOS / Linux
export IMGAPI_CARD_KEY='YOUR_16_HEX_CARD_KEY'
```

`.env.example` 仅说明配置格式；示例不会自动加载 `.env`。不要把真实 Key 提交到 Git，也不要放进浏览器代码或 `NEXT_PUBLIC_*`、`VITE_*` 等公开变量。

### Node.js

需要 Node.js 22+，无需安装依赖。

```bash
node node/run.mjs
```

### Python

需要 Python 3.10+。

```bash
python -m pip install -r python/requirements.txt
python python/run.py
```

**运行上述生成命令会提交一次真实生图任务，并按服务规则消耗积分。** 默认模型是 `gpt-image-2`，比例 `1:1`，质量 `auto`，分辨率 `1K`。在相应 `run` 文件中修改提示词和参数。

异步提交成功后，入口会先打印任务 ID，并将其保存到当前目录的 `task-id.txt`，随后轮询并输出图片 URL。请在图片链接失效前保存结果。该文件只保存最近一次任务 ID；批量或生产接入应使用自己的持久化存储。

## 恢复原任务

轮询中断或本地等待超时后，使用原任务 ID 继续查询：

```bash
node node/run.mjs --query YOUR_TASK_ID
python python/run.py --query YOUR_TASK_ID
```

这两个命令只查询，不创建新任务。提交结果不确定时，服务端可能已经受理；不要直接重新运行生成命令。如未取得任务 ID，请先到控制台核对任务记录。

## 参考图

在 Node.js 的请求参数中设置：

```js
urls: ['https://example.com/reference.png'], // 替换为真实可访问的参考图
files: ['./reference.png'],                // 本地文件路径
```

在 Python 的请求参数中设置：

```python
urls=["https://example.com/reference.png"],
files=["./reference.png"],
```

没有本地文件时使用 JSON；有本地文件时，客户端自动使用 `multipart/form-data`。`urls` 和 `files` 合计最多 12 张。`urls` 不接受 Base64 data URL；本地图片通过 `files` 上传。

## 请求契约

| 操作 | 方法与路径 | 主要字段 |
| --- | --- | --- |
| 提交生图 | `POST /tool/imgapi/draw/Async` | `key`, `model`, `prompt`, `aspectRatio`, `quality`, `resolution`, `urls` |
| 查询任务 | `POST /tool/gptimage2/query` | `key`, `id` |

地址必须保留 `/prod-api` 前缀。认证字段是请求体中的 `key`。Python 方法使用 `aspect_ratio` 参数，客户端会转换为 API 的 `aspectRatio`。

客户端来自 imgAPI 接入文档，包含参数检查、HTTP 与业务错误处理、外层 `data` 解包，以及 `id` / `task_id` / `taskId` 兼容。标准状态为 `submitted`、`processing`、`succeeded`、`failed`、`refunded`；成功结果的图片地址位于 `image`。

提交请求不会自动重试。查询临时故障会在等待预算内退避重试，并始终使用原任务 ID；默认最长等待约 10 分钟，单次请求仍有独立超时。失败或退款状态会停止等待。不要记录完整错误对象或请求体，它们可能包含敏感信息。

当前客户端列有 `gpt-image-2`、`gpt-image-2.5`、`gpt-image-2.5-flare`、`gpt-image-2.5-sunburst`、`nano-banana-2`、`nano-banana-pro`。模型可用性、参数和计费以 [imgAPI 文档](https://imgapi.vip/api-docs) 为准。

## 本地验证

```bash
npm test
python -m unittest discover -s tests -p "test_*.py"
```

测试使用模拟响应，无需真实 Key，不访问生图服务、不消耗积分。覆盖异步成功、提交失败不重复提交、失败状态、参考图上传及原任务查询。仓库验证不代表一次真实付费生成的结果。

## 文件

- `node/imgapi.mjs` / `python/imgapi.py`：从 imgAPI 文档提取的客户端。
- `node/run.mjs` / `python/run.py`：可运行入口与任务 ID 保存示例。
- `tests/`：离线契约与流程测试。

以上代码用于服务端或本地脚本接入。现有网站可在自己的服务端调用客户端，再将任务状态与图片结果返回前端。
