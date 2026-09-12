# 可运行场景 / Runnable recipes

每个 JSON 可同时交给 Node.js 和 Python 入口。文件只含生图参数；Key 来自服务端环境变量。These files contain request inputs, not measured generation results.

| 请求文件 | 用途 | 判断结果时看什么 |
| --- | --- | --- |
| [quickstart.json](quickstart.json) | 首次接入 | 是否取得任务 ID、状态及图片 URL |
| [product-photo.json](product-photo.json) | 商品主图概念稿 | 材质、瓶口结构、光线、是否出现多余文字 |
| [article-cover.json](article-cover.json) | 技术文章封面底图 | 留白、横向构图、是否方便后期加标题 |
| [reference-edit.json](reference-edit.json) | 参考图换背景 | 主体外观是否保留；运行前准备自己的 `reference.png` |

先预览，不发请求：

```bash
node node/run.mjs --dry-run --request examples/product-photo.json
python python/run.py --dry-run --request examples/article-cover.json
```

设置 `IMGAPI_CARD_KEY` 后，去掉 `--dry-run` 即提交一次付费生成。JSON 参数的基础结构会在预览时检查；模型允许值、图片文件和服务端限制在真实提交时进一步检查。

这批提示词尚未进行付费效果实测，不能作为模型质量或成功率证据。商品概念图不代表真实产品；需要保持商品外观时，在自己的请求文件中加入已授权参考图：

```json
"files": ["./reference.png"]
```

相对文件路径基于运行命令时的当前目录。也可用 `urls` 传 HTTPS 图片链接；两类参考图合计最多 12 张。不要把私有签名 URL 或客户原图提交进仓库。

参考图示例可直接这样运行，先将自己有权使用的图片放到当前目录并命名为 `reference.png`：

```bash
node node/run.mjs --request examples/reference-edit.json
# 或：python python/run.py --request examples/reference-edit.json
```

该命令会上传参考图并创建一次付费任务。使用 `--dry-run` 只展示请求，不检查图片是否存在；请在真实调用前确认文件。These commands upload your reference and create one billable task. Dry-run does not open or validate local image files.
