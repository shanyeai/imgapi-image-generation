import { writeFile } from 'node:fs/promises';
import { createImgApiClient } from './imgapi.mjs';

// Usage: node node/run.mjs [--query TASK_ID]
const args = process.argv.slice(2);
try {
  if (args.length && !(args.length === 2 && args[0] === '--query' && args[1].trim())) {
    throw new Error('Usage: node node/run.mjs [--query TASK_ID]');
  }
  const client = createImgApiClient();
  const result = args.length
    ? await client.waitForImageTask(args[1])
    : await client.generateImage({
        model: 'gpt-image-2',
        prompt: '一只戴着墨镜的柴犬坐在沙滩上喝可乐，赛博朋克风格',
        aspectRatio: '1:1', quality: 'auto', resolution: '1K',
        urls: [], files: [],
      }, {
        onTaskCreated: async taskId => {
          console.log(`Task ID: ${taskId}`);
          await writeFile('task-id.txt', taskId + '\n', 'utf8');
        },
      });
  console.log(`Task ID: ${result.taskId ?? '(synchronous result)'}`);
  console.log(result.image);
} catch (error) {
  // Do not dump the raw error, request, response or credentials.
  const key = process.env.IMGAPI_CARD_KEY;
  const message = String(error.message);
  console.error(key ? message.replaceAll(key, '[REDACTED]') : message);
  if (error.taskId) console.error(`Resume with --query ${error.taskId}`);
  process.exitCode = 1;
}
