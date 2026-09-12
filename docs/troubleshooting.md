# 排错指南 / Troubleshooting

[返回首页](../README.md)

| 现象 | 先检查 | 下一步 |
| --- | --- | --- |
| 提示 CardKey 格式错误 | `IMGAPI_CARD_KEY` 是否已设置，是否仍为占位符 | 在终端或服务端环境中设置 16 位十六进制 Key，不要公开实际值 |
| 创建 `.env` 后仍提示缺少 Key | CLI 不自动加载 `.env` | 使用 README 的环境变量命令，或沿用自己项目的服务端 env 加载方式 |
| Python 提示缺少 `httpx` | pip 和运行脚本是否是同一个 Python | `python -m pip install -r python/requirements.txt` |
| 预览通过但真实提交失败 | 预览仅检查基本 JSON 结构 | 对照模型参数、参考图文件、余额和脱敏错误信息 |
| HTTP 200 但报业务错误 | 响应 `code`、`error` 或 `msg` | 保留脱敏的业务错误和任务 ID，不将 HTTP 200 当作生成成功 |
| 提交超时，未取得 ID | 服务端可能已受理 | 查控制台任务记录；不要立刻重跑生成命令 |
| 有 ID，但等待超时或进程中断 | 本地停止等待不取消远端任务 | `--query 原任务ID` |
| 状态为 `failed` / `refunded` | 服务端失败信息 | 停止轮询；按服务文档核对后续处理，示例不会发放积分 |
| 图片路径找不到 | 相对路径基于当前运行目录 | 使用正确绝对路径或从仓库根目录运行 |
| `urls` 中的 Base64 被拒绝 | `urls` 需要 HTTPS 图片地址 | 将图片保存为本地文件，通过 `files` 上传 |
| 查询突然不能解析响应 | 模型或接口响应可能变化 | 提交脱敏后的最小复现和运行环境，不公开完整原始响应 |
| API 返回 404 | Base URL 是否缺少 `/prod-api` | 使用 `https://imgapi.vip/prod-api` 和文档中的原路径 |

获取帮助：[提交 Bug](https://github.com/shanye1402-hash/imgapi-examples/issues/new?template=bug_report.yml)。不要在公开 Issue 中粘贴 CardKey、Cookie、私人图片、带签名的下载链接或完整错误对象。

For English reports, include your OS, Node/Python version, repository commit, the command with secrets removed, and whether the failure happened before submission, during polling, or after success. A dry-run is not a live generation test. Use `--query TASK_ID` to resume; do not rerun a submission after an uncertain outcome.
