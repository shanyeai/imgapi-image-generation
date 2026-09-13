# 请求预览输出 / Request preview

[中文快速开始](../README.md#快速开始) · [English quickstart](../README.en.md#quickstart)

以下为 2026-09-13 在仓库根目录运行两种语言 CLI 后核对的输出；JSON 字段和值一致，换行格式可能随终端不同。这是离线请求预览，没有生成图片、任务 ID 或产生 API 积分消耗。

This output was checked against both CLIs on 2026-09-13. The JSON fields and values match; terminal formatting may differ. This is an offline request preview, not a generated image or a live API benchmark.

```bash
node node/run.mjs --dry-run --request examples/quickstart.json
python python/run.py --dry-run --request examples/quickstart.json
```

```json
{
  "mode": "dry-run",
  "network": false,
  "endpoint": "https://imgapi.vip/prod-api/tool/imgapi/draw/Async",
  "contentType": "application/json",
  "request": {
    "model": "gpt-image-2",
    "prompt": "一只戴着墨镜的柴犬坐在沙滩上喝可乐，赛博朋克风格",
    "aspectRatio": "1:1",
    "quality": "auto",
    "resolution": "1K",
    "urls": [],
    "files": []
  }
}
```

## 预览确认了什么

- 请求文件可读取，符合 CLI 的基本 JSON 字段和类型要求。
- 示例选择了 `gpt-image-2`、`1K`、`1:1`；这些字段可在 [quickstart.json](../examples/quickstart.json) 中修改。
- 当前命令没有调用生图接口。参考图场景的 dry-run 也不会读取或上传本地图片。

预览不验证余额、模型实时可用性、参数组合是否被服务端接受，也不证明图片效果、耗时或成功率。真实调用前查看 [API 文档](https://imgapi.vip/api-docs)，需要生成时再按快速开始配置 Key 并移除 `--dry-run`。

The preview checks basic local request structure only. It does not validate credits, live model availability, provider parameter combinations, reference file contents, image quality, latency or success rate. Configure a Key and remove `--dry-run` only when you intend to submit a billable task.
