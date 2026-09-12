const API_BASE = 'https://imgapi.vip/prod-api';
const SUBMIT_PATH = '/tool/imgapi/draw/Async';
const QUERY_PATH = '/tool/gptimage2/query';

const SUPPORTED_MODELS = new Set([
  'gpt-image-2.5',
  'gpt-image-2.5-flare',
  'gpt-image-2.5-sunburst',
  'gpt-image-2',
  'nano-banana-2',
  'nano-banana-pro',
]);
const SUPPORTED_ASPECT_RATIOS = new Set([
  'auto', '1:1', '3:2', '2:3', '16:9', '9:16', '4:3', '3:4',
  '21:9', '9:21', '1:3', '3:1', '2:1', '1:2',
]);
const SUPPORTED_QUALITIES = new Set(['auto', 'low', 'medium', 'high', 'xhigh', 'max']);
const SUPPORTED_RESOLUTIONS = new Set(['1K', '2K', '4K']);
const TRANSIENT_CODES = new Set([408, 425, 429, 500, 502, 503, 504]);

const DEFAULT_SUBMIT_TIMEOUT_MS = 60_000;
const DEFAULT_QUERY_TIMEOUT_MS = 20_000;
const DEFAULT_MAX_POLL_DURATION_MS = 10 * 60_000;
const DEFAULT_INITIAL_POLL_INTERVAL_MS = 2_000;
const DEFAULT_MAX_POLL_INTERVAL_MS = 8_000;

export class ImgApiError extends Error {
  constructor(message, options = {}) {
    super(message, options.cause ? { cause: options.cause } : undefined);
    this.name = 'ImgApiError';
    this.status = options.status ?? 0;
    this.code = options.code ?? null;
    this.retryAfterMs = options.retryAfterMs ?? 0;
    this.payload = options.payload ?? null;
    this.taskId = options.taskId ?? null;
    this.retryable = options.retryable ?? false;
    this.transportError = options.transportError ?? false;
    this.submissionUncertain = options.submissionUncertain ?? false;
  }
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function positiveNumber(value, fallback, name) {
  const number = value === undefined ? fallback : Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new TypeError(`${name} 必须是大于 0 的数字`);
  }
  return number;
}

function parseRetryAfterMs(value) {
  const text = String(value ?? '').trim();
  if (!text) return 0;

  const seconds = Number(text);
  if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);

  const moment = Date.parse(text);
  return Number.isFinite(moment) ? Math.max(0, moment - Date.now()) : 0;
}

function getRetryAfterMs(data, response) {
  const bodyValue = Number(data?.retryAfterMs);
  if (Number.isFinite(bodyValue) && bodyValue > 0) return bodyValue;
  return parseRetryAfterMs(response.headers.get('Retry-After'));
}

function getMessage(data, fallback) {
  for (const key of ['error', 'msg', 'message', 'failure_reason']) {
    const value = data?.[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return fallback;
}

function normalizeEnvelope(envelope) {
  if (!isRecord(envelope)) return null;
  return isRecord(envelope.data)
    ? { ...envelope, ...envelope.data }
    : envelope;
}

function createRequestSignal(timeoutMs, externalSignal) {
  const controller = new AbortController();
  let timedOut = false;
  let externalAborted = false;

  const onExternalAbort = () => {
    externalAborted = true;
    controller.abort(externalSignal.reason ?? new Error('操作已取消'));
  };

  if (externalSignal?.aborted) {
    onExternalAbort();
  } else if (externalSignal) {
    externalSignal.addEventListener('abort', onExternalAbort, { once: true });
  }

  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new Error(`请求超时（${timeoutMs}ms）`));
  }, timeoutMs);

  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    externalAborted: () => externalAborted,
    cleanup() {
      clearTimeout(timer);
      externalSignal?.removeEventListener('abort', onExternalAbort);
    },
  };
}

function defaultSleep(ms, signal) {
  if (signal?.aborted) {
    return Promise.reject(signal.reason ?? new Error('操作已取消'));
  }

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, Math.max(0, ms));

    const onAbort = () => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
      reject(signal.reason ?? new Error('操作已取消'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function isTransient(error) {
  return Boolean(
    error?.transportError
      || TRANSIENT_CODES.has(Number(error?.status))
      || TRANSIENT_CODES.has(Number(error?.code)),
  );
}

function withTaskId(error, taskId) {
  if (error instanceof ImgApiError) {
    if (!error.taskId) error.taskId = taskId;
    return error;
  }
  return new ImgApiError(error?.message || '查询任务失败', { taskId, cause: error });
}

function calculatePollDelay(attempt, initialMs, maxMs, random) {
  const exponential = Math.min(maxMs, initialMs * (1.5 ** Math.min(attempt, 20)));
  const jitterFactor = 0.85 + (Math.max(0, Math.min(1, random())) * 0.3);
  return Math.max(1, Math.round(exponential * jitterFactor));
}

function validateCardKey(cardKey) {
  if (!/^[0-9a-fA-F]{16}$/.test(String(cardKey ?? ''))) {
    throw new Error('请在服务端设置合法的 16 位 IMGAPI_CARD_KEY');
  }
  return String(cardKey);
}

function validateGenerateOptions(options = {}) {
  if (!isRecord(options)) throw new TypeError('生图参数必须是对象');

  const model = String(options.model ?? '');
  if (!SUPPORTED_MODELS.has(model)) {
    throw new TypeError(`model 只支持 ${[...SUPPORTED_MODELS].join('、')}`);
  }

  if (typeof options.prompt !== 'string' || !options.prompt.trim()) {
    throw new TypeError('prompt 不能为空');
  }
  if (options.prompt.length > 10000) {
    throw new TypeError('prompt 最多 10000 个字符');
  }

  const aspectRatio = options.aspectRatio ?? 'auto';
  if (!SUPPORTED_ASPECT_RATIOS.has(aspectRatio)) {
    throw new TypeError(`不支持的 aspectRatio：${aspectRatio}`);
  }

  const quality = options.quality ?? 'auto';
  if (!SUPPORTED_QUALITIES.has(quality)) {
    throw new TypeError(`不支持的 quality：${quality}`);
  }

  if (['xhigh', 'max'].includes(quality) && model !== 'gpt-image-2.5-sunburst') {
    throw new TypeError('xhigh、max 仅支持 gpt-image-2.5-sunburst');
  }
  const resolution = options.resolution ?? '1K';
  if (!SUPPORTED_RESOLUTIONS.has(resolution)) {
    throw new TypeError(`不支持的 resolution：${resolution}`);
  }

  const urls = options.urls ?? [];
  const files = options.files ?? [];
  if (!Array.isArray(urls)) throw new TypeError('urls 必须是数组');
  if (!Array.isArray(files)) throw new TypeError('files 必须是数组');
  if (urls.length + files.length > 12) {
    throw new TypeError('urls 与 files 合计最多 12 张参考图');
  }

  const normalizedUrls = urls.map((value, index) => {
    if (typeof value !== 'string' || !value.trim()) {
      throw new TypeError(`urls[${index}] 必须是 HTTPS 图片地址`);
    }
    const text = value.trim();
    let parsed;
    try {
      parsed = new URL(text);
    } catch {
      throw new TypeError(`urls[${index}] 不是合法 URL`);
    }
    if (parsed.protocol !== 'https:') {
      throw new TypeError(`urls[${index}] 必须使用 HTTPS`);
    }
    return text;
  });

  files.forEach((file, index) => {
    const isPath = typeof file === 'string' && file.trim();
    const isBlob = typeof Blob !== 'undefined' && file instanceof Blob;
    const isBuffer = typeof Buffer !== 'undefined' && Buffer.isBuffer(file);
    if (!isPath && !isBlob && !isBuffer) {
      throw new TypeError(`files[${index}] 只支持本地路径、Blob/File 或 Buffer`);
    }
  });

  return {
    model,
    prompt: options.prompt,
    aspectRatio,
    quality,
    resolution,
    urls: normalizedUrls,
    files: [...files],
  };
}

function mimeTypeFromFilename(filename) {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  if (lower.endsWith('.webp')) return 'image/webp';
  if (lower.endsWith('.gif')) return 'image/gif';
  if (lower.endsWith('.avif')) return 'image/avif';
  return 'application/octet-stream';
}

async function appendLocalFile(form, file, index) {
  if (typeof file === 'string') {
    const [{ readFile }, { basename }] = await Promise.all([
      import('node:fs/promises'),
      import('node:path'),
    ]);
    const filename = basename(file);
    const bytes = await readFile(file);
    form.append('files', new Blob([bytes], { type: mimeTypeFromFilename(filename) }), filename);
    return;
  }

  if (typeof Buffer !== 'undefined' && Buffer.isBuffer(file)) {
    form.append('files', new Blob([file]), `reference-${index + 1}`);
    return;
  }

  const filename = typeof file.name === 'string' && file.name
    ? file.name
    : `reference-${index + 1}`;
  form.append('files', file, filename);
}

async function createGenerateRequest(options, cardKey) {
  const fields = {
    key: cardKey,
    model: options.model,
    prompt: options.prompt,
    aspectRatio: options.aspectRatio,
    quality: options.quality,
    resolution: options.resolution,
  };

  if (options.files.length === 0) {
    return {
      body: { ...fields, urls: options.urls },
      isFormData: false,
    };
  }

  const form = new FormData();
  for (const [name, value] of Object.entries(fields)) {
    form.append(name, String(value));
  }
  for (const url of options.urls) form.append('urls', url);
  for (const [index, file] of options.files.entries()) {
    await appendLocalFile(form, file, index);
  }

  return { body: form, isFormData: true };
}

function extractTaskId(data) {
  const taskId = data?.id ?? data?.task_id ?? data?.taskId;
  return taskId === undefined || taskId === null || String(taskId).trim() === ''
    ? null
    : String(taskId);
}

export function createImgApiClient({
  cardKey = process.env.IMGAPI_CARD_KEY,
  fetchImpl = globalThis.fetch,
  sleepImpl = defaultSleep,
  now = () => performance.now(),
  random = Math.random,
} = {}) {
  const key = validateCardKey(cardKey);
  if (typeof fetchImpl !== 'function') throw new Error('当前 Node.js 环境不支持 fetch，请使用 Node.js 18+');
  if (typeof sleepImpl !== 'function' || typeof now !== 'function' || typeof random !== 'function') {
    throw new TypeError('fetch/sleep/now/random 配置无效');
  }

  async function post(path, body, {
    isFormData = false,
    timeoutMs,
    signal,
  } = {}) {
    const timeout = positiveNumber(timeoutMs, DEFAULT_QUERY_TIMEOUT_MS, 'timeoutMs');
    const requestSignal = createRequestSignal(timeout, signal);
    let response;
    let raw;

    try {
      response = await fetchImpl(`${API_BASE}${path}`, {
        method: 'POST',
        headers: isFormData
          ? { Accept: 'application/json' }
          : { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: isFormData ? body : JSON.stringify(body),
        signal: requestSignal.signal,
      });
      raw = await response.text();
    } catch (cause) {
      if (requestSignal.externalAborted()) {
        throw new ImgApiError('操作已取消', { cause });
      }
      const message = requestSignal.timedOut()
        ? `请求超时（${timeout}ms）`
        : `网络请求失败：${cause?.message || 'unknown error'}`;
      throw new ImgApiError(message, {
        cause,
        retryable: true,
        transportError: true,
      });
    } finally {
      requestSignal.cleanup();
    }

    let envelope = {};
    if (raw?.trim()) {
      try {
        envelope = JSON.parse(raw);
      } catch (cause) {
        throw new ImgApiError(
          response.ok
            ? '接口返回了无法解析的非 JSON 响应'
            : `请求失败（HTTP ${response.status}，响应不是 JSON）`,
          {
            status: response.status,
            retryable: response.status >= 500,
            cause,
          },
        );
      }
    }

    const data = normalizeEnvelope(envelope);
    if (!data) {
      throw new ImgApiError('接口返回的 JSON 不是对象', {
        status: response.status,
        retryable: response.status >= 500,
      });
    }

    const hasBusinessCode = Object.hasOwn(data, 'code');
    const businessFailed = data.ok === false
      || (hasBusinessCode && Number(data.code) !== 200);

    if (!response.ok || businessFailed) {
      const status = response.status;
      const code = data.code ?? null;
      throw new ImgApiError(
        getMessage(data, `请求失败（HTTP ${status}）`),
        {
          status,
          code,
          retryAfterMs: getRetryAfterMs(data, response),
          payload: data,
          retryable: TRANSIENT_CODES.has(Number(status)) || TRANSIENT_CODES.has(Number(code)),
        },
      );
    }

    return data;
  }

  async function submitImageTask(options, {
    signal,
    submitTimeoutMs = DEFAULT_SUBMIT_TIMEOUT_MS,
    onTaskCreated,
  } = {}) {
    const normalized = validateGenerateOptions(options);
    const request = await createGenerateRequest(normalized, key);
    let submitted;

    try {
      submitted = await post(SUBMIT_PATH, request.body, {
        isFormData: request.isFormData,
        timeoutMs: submitTimeoutMs,
        signal,
      });
    } catch (error) {
      const status = Number(error?.status || 0);
      const uncertain = Boolean(error?.transportError || status === 408 || status >= 500);
      if (uncertain) {
        throw new ImgApiError(
          `提交结果不确定：${error.message}；禁止自动重新提交，以免产生重复任务或重复扣费`,
          {
            status: error.status,
            code: error.code,
            payload: error.payload,
            retryAfterMs: error.retryAfterMs,
            cause: error,
            submissionUncertain: true,
          },
        );
      }
      throw error;
    }

    const status = String(submitted.status ?? '').toLowerCase();
    const taskId = extractTaskId(submitted);

    if (status === 'succeeded') {
      if (typeof submitted.image !== 'string' || !submitted.image.trim()) {
        throw new ImgApiError('任务状态为 succeeded，但响应缺少 image', {
          taskId,
          payload: submitted,
        });
      }
      return { taskId, status, image: submitted.image, raw: submitted };
    }

    if (status === 'failed' || status === 'refunded') {
      throw new ImgApiError(getMessage(submitted, '生成失败'), {
        taskId,
        payload: submitted,
      });
    }

    if (!taskId) {
      throw new ImgApiError('提交接口未返回任务 ID', { payload: submitted });
    }

    if (onTaskCreated) {
      try {
        await onTaskCreated(taskId, submitted);
      } catch (cause) {
        throw new ImgApiError(
          '任务已经提交，但保存任务 ID 失败；请使用错误中的 taskId 继续查询，禁止重新提交',
          { taskId, payload: submitted, cause },
        );
      }
    }

    return {
      taskId,
      status: status || 'submitted',
      image: null,
      raw: submitted,
    };
  }

  async function queryImageTask(taskId, {
    signal,
    queryTimeoutMs = DEFAULT_QUERY_TIMEOUT_MS,
  } = {}) {
    const id = String(taskId ?? '').trim();
    if (!id) throw new TypeError('taskId 不能为空');

    try {
      return await post(QUERY_PATH, { key, id }, {
        timeoutMs: queryTimeoutMs,
        signal,
      });
    } catch (error) {
      throw withTaskId(error, id);
    }
  }

  async function waitForImageTask(taskId, {
    signal,
    queryTimeoutMs = DEFAULT_QUERY_TIMEOUT_MS,
    maxPollDurationMs = DEFAULT_MAX_POLL_DURATION_MS,
    initialPollIntervalMs = DEFAULT_INITIAL_POLL_INTERVAL_MS,
    maxPollIntervalMs = DEFAULT_MAX_POLL_INTERVAL_MS,
    onPoll,
  } = {}) {
    const id = String(taskId ?? '').trim();
    if (!id) throw new TypeError('taskId 不能为空');

    const maxDuration = positiveNumber(maxPollDurationMs, DEFAULT_MAX_POLL_DURATION_MS, 'maxPollDurationMs');
    const initialInterval = positiveNumber(initialPollIntervalMs, DEFAULT_INITIAL_POLL_INTERVAL_MS, 'initialPollIntervalMs');
    const maxInterval = positiveNumber(maxPollIntervalMs, DEFAULT_MAX_POLL_INTERVAL_MS, 'maxPollIntervalMs');
    if (maxInterval < initialInterval) {
      throw new TypeError('maxPollIntervalMs 不能小于 initialPollIntervalMs');
    }

    const startedAt = now();
    let attempt = 0;
    let nextDelayMs = initialInterval;

    while (now() - startedAt < maxDuration) {
      const remainingBeforeSleep = maxDuration - (now() - startedAt);
      try {
        await sleepImpl(Math.min(nextDelayMs, remainingBeforeSleep), signal);
      } catch (cause) {
        throw new ImgApiError(
          '已停止本地等待；服务端任务可能仍在运行，请使用 taskId 继续查询',
          { taskId: id, cause },
        );
      }

      if (now() - startedAt >= maxDuration) break;

      let queried;
      try {
        queried = await queryImageTask(id, { signal, queryTimeoutMs });
      } catch (error) {
        if (!isTransient(error)) throw withTaskId(error, id);
        attempt += 1;
        nextDelayMs = error.retryAfterMs > 0
          ? error.retryAfterMs
          : calculatePollDelay(attempt, initialInterval, maxInterval, random);
        await onPoll?.({
          taskId: id,
          attempt,
          status: 'retrying',
          nextDelayMs,
          error,
        });
        continue;
      }

      const status = String(queried.status ?? '').toLowerCase();
      await onPoll?.({ taskId: id, attempt, status, response: queried });

      if (status === 'succeeded') {
        if (typeof queried.image !== 'string' || !queried.image.trim()) {
          throw new ImgApiError('任务状态为 succeeded，但响应缺少 image', {
            taskId: id,
            payload: queried,
          });
        }
        return { taskId: id, status, image: queried.image, raw: queried };
      }

      if (status === 'failed' || status === 'refunded') {
        throw new ImgApiError(getMessage(queried, '生成失败'), {
          taskId: id,
          payload: queried,
        });
      }

      if (status !== 'submitted' && status !== 'processing') {
        throw new ImgApiError(`接口返回了未知任务状态：${status || 'empty'}`, {
          taskId: id,
          payload: queried,
        });
      }

      attempt += 1;
      nextDelayMs = calculatePollDelay(attempt, initialInterval, maxInterval, random);
    }

    throw new ImgApiError(
      '生成时间较长；服务端任务可能仍在运行，请保存 taskId 并稍后继续查询',
      { taskId: id },
    );
  }

  async function generateImage(options, waitOptions = {}) {
    const submitted = await submitImageTask(options, waitOptions);
    if (submitted.image) return submitted;
    return waitForImageTask(submitted.taskId, waitOptions);
  }

  return {
    submitImageTask,
    queryImageTask,
    waitForImageTask,
    generateImage,
  };
}
