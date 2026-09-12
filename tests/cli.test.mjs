import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createImgApiClient } from '../node/imgapi.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const run = new URL('../node/run.mjs', import.meta.url);
function cli(args, cwd = root) {
  return spawnSync(process.execPath, ['--import', 'data:text/javascript,globalThis.fetch=()=>{throw new Error("NETWORK_FORBIDDEN")}', fileURLToPath(run), ...args], {
    cwd, encoding: 'utf8', env: { ...process.env, IMGAPI_CARD_KEY: '' }, timeout: 10000,
  });
}

test('every recipe previews without credentials and submits valid fields to a mock', async () => {
  for (const name of ['quickstart', 'product-photo', 'article-cover']) {
    const path = `examples/${name}.json`;
    const result = cli(['--dry-run', '--request', path]);
    assert.equal(result.status, 0, result.stderr);
    const preview = JSON.parse(result.stdout);
    assert.equal(preview.mode, 'dry-run');
    assert.equal(preview.network, false);
    assert.equal(preview.request.key, undefined);
    const client = createImgApiClient({ cardKey: '0123456789abcdef', fetchImpl: async (_, init) => {
      assert.equal(JSON.parse(init.body).prompt, preview.request.prompt);
      return new Response(JSON.stringify({ code: 200, status: 'succeeded', image: 'https://example.com/result.png' }));
    } });
    await client.submitImageTask(preview.request);
  }
});

test('default request resolves outside repository; help makes no network call', () => {
  const result = cli(['--dry-run'], tmpdir());
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).request.model, 'gpt-image-2');
  assert.equal(cli(['--help']).status, 0);
});

test('ambiguous or unknown CLI flags are rejected before networking', () => {
  for (const args of [['--query', 'task', '--dry-run'], ['--query', 'task', '--request', 'x'], ['--query', ''], ['--unknown']]) {
    const result = cli(args);
    assert.notEqual(result.status, 0);
    assert.doesNotMatch(result.stderr, /NETWORK_FORBIDDEN/);
  }
});

test('malformed and credential-bearing request files fail without echoing contents', () => {
  const directory = mkdtempSync(join(tmpdir(), 'imgapi-cli-'));
  try {
    for (const contents of ['{"key":"sensitive-placeholder","model":"gpt-image-2","prompt":"x"}', '{"key":"sensitive-placeholder"', '[]', '{"model":"x","prompt":"x","files":null}']) {
      const path = join(directory, 'request.json');
      writeFileSync(path, contents);
      const result = cli(['--dry-run', '--request', path]);
      assert.notEqual(result.status, 0);
      assert.doesNotMatch(result.stdout + result.stderr, /sensitive-placeholder|NETWORK_FORBIDDEN/);
    }
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('real entrypoint saves async ID and query mode does not submit', () => {
  const directory = mkdtempSync(join(tmpdir(), 'imgapi-entry-'));
  const execute = query => spawnSync(process.execPath, ['--input-type=module', '-e', `
    import assert from 'node:assert/strict';
    process.argv = ['node', ${JSON.stringify(fileURLToPath(run))}, ...${JSON.stringify(query ? ['--query', 'cli-task'] : [])}];
    let calls = 0;
    globalThis.fetch = async (url, init) => {
      calls++;
      if (${query}) assert.ok(url.endsWith('/query'));
      else if (calls === 1) {
        assert.ok(url.endsWith('/draw/Async'));
        return new Response(JSON.stringify({code:200, status:'submitted', taskId:'cli-task'}));
      }
      assert.equal(JSON.parse(init.body).id, 'cli-task');
      return new Response(JSON.stringify({code:200, status:'succeeded', image:'https://example.com/result.png'}));
    };
    await import(${JSON.stringify(run.href)});
    assert.equal(calls, ${query ? 1 : 2});
  `], { cwd: directory, encoding: 'utf8', env: { ...process.env, IMGAPI_CARD_KEY: '0123456789abcdef' }, timeout: 10000 });
  try {
    const first = execute(false);
    assert.equal(first.status, 0, first.stderr);
    assert.equal(readFileSync(join(directory, 'task-id.txt'), 'utf8').trim(), 'cli-task');
    const resumed = execute(true);
    assert.equal(resumed.status, 0, resumed.stderr);
    assert.match(resumed.stdout, /https:\/\/example.com\/result.png/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});
