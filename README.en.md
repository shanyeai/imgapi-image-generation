<p>
<a href="https://imgapi.vip/"><picture>
  <source media="(max-width: 600px)" srcset="assets/readme-hero-mobile.svg">
  <img src="assets/readme-hero.svg" alt="imgAPI AI image generation API — Node.js / Python" width="1280">
</picture></a>
</p>

# imgAPI — AI Image Generation API Examples

**Node.js and Python examples** for GPT Image 2, GPT Image 2.5 and Nano Banana: text-to-image, reference images and asynchronous task polling.

[Get an API Key](https://imgapi.vip/) · [API docs & pricing](https://imgapi.vip/api-docs) · [Quickstart](#quickstart) · [简体中文](README.md)

[![Offline tests](https://github.com/shanye1402-hash/imgapi-image-generation/actions/workflows/test.yml/badge.svg)](https://github.com/shanye1402-hash/imgapi-image-generation/actions/workflows/test.yml)

## Quickstart

Requires Node.js 22+ or Python 3.10+. Choose either runtime.

```bash
git clone https://github.com/shanye1402-hash/imgapi-image-generation.git
cd imgapi-image-generation
```

**1. Set your Key.** Get a CardKey from [imgapi.vip](https://imgapi.vip/) and replace the placeholder.

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

**2. Generate one image.** The default is GPT Image 2, 1K, 1:1. This submits one real task and uses credits under the service's billing rules.

```bash
# Node.js: no dependencies required
node node/run.mjs --request examples/quickstart.json
```

```bash
# Python
python -m pip install -r python/requirements.txt
python python/run.py --request examples/quickstart.json
```

On success, the CLI prints the **task ID and image URL**. Asynchronous IDs are saved to `task-id.txt` in your current directory. Download the result yourself before the URL expires.

To preview a request, add `--dry-run`: no Key, network calls or credits needed. The scripts do not load `.env` automatically. Keep your Key in a terminal or server environment.

## Choose an example

Both languages accept the same JSON. Replace the `--request` file above:

| Use case | Request file | What to change |
| --- | --- | --- |
| Text to image | [quickstart.json](examples/quickstart.json) | `prompt` |
| Product photo concept | [product-photo.json](examples/product-photo.json) | Product description |
| Article cover | [article-cover.json](examples/article-cover.json) | Topic and composition |
| Image to image | [reference-edit.json](examples/reference-edit.json) | Supply your own `reference.png` |

[Reference image and parameter notes](examples/README.md). These are input recipes, not paid generation benchmarks.

## Supported models

| Model | JSON `model` value |
| --- | --- |
| GPT Image 2 | `gpt-image-2` |
| GPT Image 2.5 | `gpt-image-2.5`, `gpt-image-2.5-flare`, `gpt-image-2.5-sunburst` |
| Nano Banana 2 | `nano-banana-2` |
| Nano Banana Pro | `nano-banana-pro` |

Edit `model` in the request JSON. See [imgAPI documentation](https://imgapi.vip/api-docs) for current availability, supported parameter combinations and pricing.

## Resume or integrate

Resume an existing task with `node node/run.mjs --query YOUR_TASK_ID` or `python python/run.py --query YOUR_TASK_ID`. If submission is uncertain, check the dashboard before creating another task.

Import [`createImgApiClient`](node/imgapi.mjs) or [`ImgApiClient`](python/imgapi.py) into an existing application; see the [integration guide](docs/integration.md). This API uses its own JSON protocol, not a drop-in OpenAI SDK base URL.

[Troubleshooting](docs/troubleshooting.md) · [Issues](https://github.com/shanye1402-hash/imgapi-image-generation/issues) · [Contributing & offline tests](CONTRIBUTING.md) · [Creator kit](docs/creator-kit.md)

No open-source license has been granted; contact the maintainer for reuse permissions where required. CI validates offline examples, not live image quality or service uptime.
