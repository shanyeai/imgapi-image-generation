# 接入指南

[返回首页](../README.md) · [English quickstart](../README.en.md)

## 选入口

| 场景 | 推荐方式 |
| --- | --- |
| 本地验证参数 | `--dry-run --request examples/product-photo.json` |
| 本地单次生成 | 设置 Key 后移除 `--dry-run` |
| 已有 Node.js 应用 | 导入 `createImgApiClient` |
| 已有 Python 应用 | 导入 `ImgApiClient` |
| 浏览器应用 | 浏览器调用自己的服务端；由服务端调用 imgAPI |

以下片段假设代码位于仓库根目录。执行生成方法会创建真实付费任务。

### Node.js

```js
import { createImgApiClient } from './node/imgapi.mjs';
import { readFile, writeFile } from 'node:fs/promises';

const client = createImgApiClient(); // Reads IMGAPI_CARD_KEY
const request = JSON.parse(await readFile('examples/product-photo.json', 'utf8'));
const result = await client.generateImage(request, {
  onTaskCreated: async taskId => {
    console.log('Task ID:', taskId);
    await writeFile('task-id.txt', taskId + '\n', 'utf8');
  },
});
console.log(result.image);
```

### Python

从仓库根目录运行临时脚本时，可将客户端目录加入导入路径；已有应用可把客户端放进自己的 Python 包。

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "python"))
from imgapi import ImgApiClient

def save_task(task_id):
    print("Task ID:", task_id, flush=True)
    Path("task-id.txt").write_text(task_id + "\n", encoding="utf-8")

request = json.loads(Path("examples/product-photo.json").read_text(encoding="utf-8"))
with ImgApiClient() as client:
    result = client.generate_image(request, on_task_created=save_task)
print(result.image_url)
```

## 请求字段

| JSON 字段 | 说明 |
| --- | --- |
| `model` | 模型 ID，默认示例使用 `gpt-image-2` |
| `prompt` | 非空提示词；客户端限制最多 10000 个字符 |
| `aspectRatio` | 比例，如 `1:1`、`16:9`、`3:4` |
| `quality` | 常用 `auto`、`low`、`medium`、`high`；扩展档位受模型限制 |
| `resolution` | `1K`、`2K`、`4K`，当前可用组合以服务文档为准 |
| `urls` | HTTPS 参考图链接数组 |
| `files` | 本地参考图路径数组；与 `urls` 合计最多 12 张 |

CLI 请求文件只允许这些字段。不得包含 `key`；它由环境变量注入。Python 使用关键字参数时可写 `aspect_ratio`，共享 JSON 使用 API 原字段 `aspectRatio`。

无本地文件时提交 JSON；有本地文件时，客户端组装 `multipart/form-data`，不要手动写 boundary 或 Content-Type。`--dry-run` 不打开参考图文件，真实调用才检查和上传文件。

## 查询与错误

- HTTP 成功仍需检查业务 `code`；两套客户端已处理外层 `data` 包装。
- 提交不会自动重试。提交结果不确定时，先核对任务记录。
- 查询遇到临时错误会退避后继续查原 ID；默认等待预算约 10 分钟，单次请求另有超时。
- `failed`、`refunded` 停止等待；等待结束不等于服务端任务被取消。
- 错误对象可能含请求响应上下文。仅记录脱敏后的信息与任务 ID，不打印整个对象。

## 放进生产应用前

示例只处理一次本地任务。Web 接入还需使用项目已有的用户认证、额度约束和任务存储：把任务 ID 关联到发起用户；查询时验证归属；保存任务 ID 后再更新页面。不要暴露一个携带你的 Key、任何人都能调用的公开生成接口。

Node 客户端提供异步方法；Python 客户端为同步 HTTPX 实现。Python 异步 Web 服务应使用现有的后台任务机制或线程执行方式，避免在事件循环里直接阻塞等待。不要因为浏览器刷新重新提交同一任务。

更换模型不需要改接口路径。此服务使用自己的 JSON 协议，不能仅修改 OpenAI SDK 的 base URL 完成兼容。仓库没有发布 npm/PyPI SDK 包。
