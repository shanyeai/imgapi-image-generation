import test from 'node:test';
import assert from 'node:assert/strict';
import { createImgApiClient } from '../node/imgapi.mjs';

const options = { model: 'gpt-image-2', prompt: 'test', resolution: '1K' };
const key = '0123456789abcdef'; // Deliberately fake fixture, never sent to a network.
function mock(responses) {
  const calls = [];
  const client = createImgApiClient({
    cardKey: key, sleepImpl: async () => {},
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      assert.ok(responses.length, 'Unexpected extra request');
      const data = responses.shift();
      if (data instanceof Error) throw data;
      return new Response(JSON.stringify(data), { status: 200 });
    },
  });
  return { client, calls };
}

test('submits once, records task ID before polling, unwraps result', async () => {
  const { client, calls } = mock([
    { code: 200, data: { task_id: 'task-1', status: 'submitted' } },
    { code: 200, status: 'processing' },
    { code: 200, data: { status: 'succeeded', image: 'https://example.com/result.png' } },
  ]);
  const result = await client.generateImage(options, {
    onTaskCreated: id => { assert.equal(id, 'task-1'); assert.equal(calls.length, 1); },
  });
  assert.equal(result.image, 'https://example.com/result.png');
  assert.equal(calls[0].url, 'https://imgapi.vip/prod-api/tool/imgapi/draw/Async');
  assert.equal(JSON.parse(calls[0].init.body).key, key);
  for (const call of calls.slice(1)) {
    assert.equal(call.url, 'https://imgapi.vip/prod-api/tool/gptimage2/query');
    assert.deepEqual(JSON.parse(call.init.body), { key, id: 'task-1' });
  }
});

test('uncertain submission never resubmits', async () => {
  const { client, calls } = mock([new TypeError('network disconnected')]);
  await assert.rejects(client.generateImage(options), error => error.submissionUncertain === true);
  assert.equal(calls.length, 1);
});

test('resume only queries and stops on refund', async () => {
  const { client, calls } = mock([{ code: 200, status: 'refunded', error: 'refunded' }]);
  await assert.rejects(client.waitForImageTask('existing'), error => error.taskId === 'existing');
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith('/query'));
});

test('multipart carries files and URLs without manual content type', async () => {
  const { client, calls } = mock([{ code: 200, taskId: 'multipart', status: 'submitted' }]);
  await client.submitImageTask({ ...options, files: [new Blob(['mock image'])], urls: ['https://example.com/ref.png'] });
  const { init } = calls[0];
  assert.ok(init.body instanceof FormData);
  assert.equal(init.body.getAll('files').length, 1);
  assert.equal(init.body.get('urls'), 'https://example.com/ref.png');
  assert.equal(new Headers(init.headers).has('Content-Type'), false);
});

test('business failure and invalid inputs do not create more tasks', async () => {
  const { client, calls } = mock([{ code: 500, msg: 'failure' }]);
  await assert.rejects(client.submitImageTask(options));
  await assert.rejects(client.submitImageTask({ ...options, model: 'invalid' }));
  assert.equal(calls.length, 1);
});
