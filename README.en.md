# imgAPI · AI Image Generation API Examples

**Connect image generation to your application with Node.js or Python. Includes reference images, asynchronous polling and task recovery.**

[简体中文](README.md) · [imgapi.vip](https://imgapi.vip/) · [API documentation](https://imgapi.vip/api-docs) · [Recipes](examples/README.md) · [Creator kit](docs/creator-kit.md)

[![Offline tests](https://github.com/shanye1402-hash/imgapi-examples/actions/workflows/test.yml/badge.svg)](https://github.com/shanye1402-hash/imgapi-examples/actions/workflows/test.yml)

Use these examples for product image concepts, article cover backgrounds or server-side image generation. The default model is `gpt-image-2`. Client options also include GPT Image 2.5, Nano Banana 2 and Nano Banana Pro; check the service documentation for current availability and pricing.

## Try a request preview without a Key

Requires Node.js 22+ or Python 3.10+.

```bash
git clone https://github.com/shanye1402-hash/imgapi-examples.git
cd imgapi-examples
node node/run.mjs --dry-run
# Or: python python/run.py --dry-run
```

This prints `mode: "dry-run"`, `network: false`, the endpoint and request fields. It makes no network requests, generates no image and uses no credits. Python dry-run requires no third-party packages. It checks basic JSON structure, not provider constraints or reference file availability.

## Pick a recipe

| Input | Use case |
| --- | --- |
| [quickstart.json](examples/quickstart.json) | First integration |
| [product-photo.json](examples/product-photo.json) | Unbranded product photo concept |
| [article-cover.json](examples/article-cover.json) | Technical article cover background |

```bash
node node/run.mjs --dry-run --request examples/product-photo.json
python python/run.py --dry-run --request examples/article-cover.json
```

Both languages accept the same JSON file. Prompts can be edited or translated. These inputs have not been evaluated with paid generation calls; they are not quality benchmarks.

## Generate an image

Get a CardKey from [imgAPI](https://imgapi.vip/), then set a terminal or server environment variable. Replace the placeholder with your 16-character hexadecimal Key.

```bash
export IMGAPI_CARD_KEY='YOUR_16_HEX_CARD_KEY'
```

```powershell
# Windows PowerShell
$env:IMGAPI_CARD_KEY = 'YOUR_16_HEX_CARD_KEY'
```

Node.js requires no dependencies:

```bash
node node/run.mjs --request examples/product-photo.json
```

For Python:

```bash
python -m pip install -r python/requirements.txt
python python/run.py --request examples/product-photo.json
```

**Removing `--dry-run` submits one real task and uses credits according to the service's billing rules.** `.env` is not loaded automatically. Keep credentials out of JSON files, Git, browser code and public environment variables.

The CLI prints an asynchronous task ID and saves it to `task-id.txt` in your current directory before polling. It prints the image URL when successful; it does not download the image. A synchronous result may return an image immediately.

## Resume instead of submitting again

```bash
node node/run.mjs --query YOUR_TASK_ID
python python/run.py --query YOUR_TASK_ID
```

These commands only query the original task. A submission timeout does not prove the server rejected it. If you did not receive an ID, check the dashboard before submitting again. The local task file stores only the most recent asynchronous ID; use your own persistence for multiple jobs.

## Reference images

Set `files` to local paths or `urls` to HTTPS image URLs in your request JSON. Local paths are relative to the current working directory, not the JSON file. The client automatically switches to multipart when local files are present. The combined limit is 12 references. Base64 data URLs are not accepted in `urls`.

## Integration and support

The API base is `https://imgapi.vip/prod-api`. Submit with `POST /tool/imgapi/draw/Async`; query with `POST /tool/gptimage2/query`. Authentication uses the `key` field in the request body. This is not a drop-in OpenAI SDK endpoint.

- [Integration guide](docs/integration.md): imports, parameters and application boundaries.
- [Troubleshooting](docs/troubleshooting.md): credentials, errors and task recovery.
- [Contributing](CONTRIBUTING.md): bug reports and new recipes.
- [Issues](https://github.com/shanye1402-hash/imgapi-examples/issues): report a reproducible problem or share an integration.

```bash
npm test
python -m pip install -r python/requirements.txt
python -m unittest discover -s tests -p "test_*.py"
```

Tests use offline fixtures and no real credentials. CI does not measure API uptime, speed or image quality.

No open-source license has been granted for this repository. Contact the repository owner before reuse that requires permission.
