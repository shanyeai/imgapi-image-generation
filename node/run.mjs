import { readFile, writeFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { createImgApiClient } from './imgapi.mjs';

try {
  const { values } = parseArgs({ args: process.argv.slice(2), options: {
    'dry-run': { type: 'boolean' },
    request: { type: 'string' },
    query: { type: 'string' },
    help: { type: 'boolean', short: 'h' },
  } });
  if (values.help) {
    console.log('Usage: node node/run.mjs [--dry-run] [--request examples/product-photo.json]\n       node node/run.mjs --query TASK_ID\nWithout --dry-run or --query, submits ONE billable image task.');
  } else if (values.query !== undefined && (values['dry-run'] || values.request !== undefined || !values.query.trim())) {
    throw new Error('--query requires a task ID and cannot be combined with --request or --dry-run');
  } else if (values.query !== undefined) {
    const result = await createImgApiClient().waitForImageTask(values.query);
    console.log(`Task ID: ${result.taskId}`);
    console.log(result.image);
  } else {
    const source = values.request ?? new URL('../examples/quickstart.json', import.meta.url);
    let request;
    try { request = JSON.parse(await readFile(source, 'utf8')); }
    catch (error) { throw new Error(error.code ? `Cannot read request file (${error.code})` : 'Request file must be valid UTF-8 JSON'); }
    const allowed = new Set(['model', 'prompt', 'aspectRatio', 'quality', 'resolution', 'urls', 'files']);
    if (!request || Array.isArray(request) || typeof request !== 'object' || Object.keys(request).some(key => !allowed.has(key))) {
      throw new Error('Request JSON must contain only model, prompt, aspectRatio, quality, resolution, urls and files; never put credentials in it');
    }
    if (typeof request.model !== 'string' || !request.model.trim() || typeof request.prompt !== 'string' || !request.prompt.trim()) {
      throw new Error('Request JSON requires non-empty model and prompt strings');
    }
    for (const field of ['aspectRatio', 'quality', 'resolution']) {
      if (request[field] !== undefined && typeof request[field] !== 'string') throw new Error(`${field} must be a string`);
    }
    for (const field of ['urls', 'files']) {
      if (request[field] !== undefined && (!Array.isArray(request[field]) || request[field].some(value => typeof value !== 'string' || !value.trim()))) throw new Error(`${field} must be an array of non-empty strings`);
    }
    if (values['dry-run']) {
      // Preview only. Provider validation and local file reads happen on submission.
      console.log(JSON.stringify({ mode: 'dry-run', network: false,
        endpoint: 'https://imgapi.vip/prod-api/tool/imgapi/draw/Async',
        contentType: request.files?.length ? 'multipart/form-data' : 'application/json', request }, null, 2));
    } else {
      const client = createImgApiClient();
      console.error('Submitting ONE billable task. No automatic resubmission.');
      const result = await client.generateImage(request, {
        onTaskCreated: async taskId => {
          console.log(`Task ID: ${taskId}`);
          await writeFile('task-id.txt', taskId + '\n', 'utf8');
        },
      });
      console.log(`Task ID: ${result.taskId ?? '(synchronous result)'}`);
      console.log(result.image);
    }
  }
} catch (error) {
  // Do not dump the raw error, request, response or credentials.
  const key = process.env.IMGAPI_CARD_KEY;
  const message = String(error.message);
  console.error(key ? message.replaceAll(key, '[REDACTED]') : message);
  if (error.taskId) console.error(`Resume with --query ${error.taskId}`);
  process.exitCode = 1;
}
