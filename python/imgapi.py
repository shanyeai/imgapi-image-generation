"""
imgAPI 生产增强版同步 Python 客户端。

依赖：
    pip install "httpx>=0.27,<1"

安全原则：
- CardKey 只从服务端环境变量或构造参数读取，不写入浏览器代码。
- 提交任务不会自动重试；提交超时或响应中断时，服务端可能已经创建任务。
- 查询失败时始终复用原 task_id，不重新提交生成任务。
- 使用本地文件时，HTTPX 会以 multipart/form-data 流式上传。

Python：3.10+
"""

from __future__ import annotations

import json
import inspect
import math
import mimetypes
import os
import random
import re
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeAlias
from urllib.parse import urlsplit

import httpx


API_BASE = "https://imgapi.vip/prod-api"
GENERATE_PATH = "/tool/imgapi/draw/Async"
QUERY_PATH = "/tool/gptimage2/query"

SUPPORTED_MODELS = frozenset({
    "gpt-image-2.5",
    "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst",
    "gpt-image-2",
    "nano-banana-2",
    "nano-banana-pro",
})
SUPPORTED_QUALITIES = frozenset({"auto", "low", "medium", "high", "xhigh", "max"})
SUPPORTED_RESOLUTIONS = frozenset({"1K", "2K", "4K"})

MAX_PROMPT_LENGTH = 10000
MAX_REFERENCE_IMAGES = 12
DEFAULT_POLL_DURATION_SECONDS = 10 * 60
DEFAULT_MAX_POLL_ATTEMPTS = 300

PENDING_STATUSES = frozenset({"submitted", "processing", "pending", "queued", "running"})
SUCCEEDED_STATUSES = frozenset({"succeeded", "success", "completed"})
FAILED_STATUSES = frozenset({"failed", "refunded", "cancelled", "canceled"})

RETRYABLE_QUERY_HTTP_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
AMBIGUOUS_SUBMISSION_HTTP_STATUSES = frozenset({408, 425, 500, 502, 503, 504})

PathInput: TypeAlias = str | os.PathLike[str]
TaskCreatedCallback: TypeAlias = Callable[..., None]
StatusCallback: TypeAlias = Callable[["TaskSnapshot"], None]
CancelCallback: TypeAlias = Callable[[], bool]


class ImgApiError(Exception):
    """所有 imgAPI 客户端异常的基类。"""

    def __init__(
        self,
        message: str,
        *,
        status: int = 0,
        code: Any = None,
        retry_after_ms: int = 0,
        payload: Mapping[str, Any] | None = None,
        task_id: str | None = None,
        submission_uncertain: bool = False,
        definitely_not_sent: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = int(status or 0)
        self.code = code
        self.retry_after_ms = max(0, int(retry_after_ms or 0))
        self.payload = dict(payload or {})
        self.task_id = task_id
        self.submission_uncertain = bool(submission_uncertain)
        self.definitely_not_sent = bool(definitely_not_sent)


class ValidationError(ImgApiError):
    """调用参数不符合要求。"""


class TransportError(ImgApiError):
    """网络、连接池或底层传输错误。"""


class ProtocolError(ImgApiError):
    """HTTP 成功，但服务端响应结构不符合接口约定。"""


class ApiResponseError(ImgApiError):
    """HTTP 或业务状态明确返回失败。"""


class SubmissionUncertainError(ImgApiError):
    """提交结果不确定；禁止自动重新提交，以免重复任务或重复扣费。"""


class TaskFailedError(ImgApiError):
    """生成任务明确失败、退款或取消。"""


class TaskPersistenceError(ImgApiError):
    """服务端已经返回 task_id，但调用方未能持久化该 ID。"""


class TaskCallbackError(ImgApiError):
    """任务状态回调执行失败。"""


class PollTimeoutError(ImgApiError):
    """达到轮询时长或次数上限，任务可能仍在服务端执行。"""


class PollCancelledError(ImgApiError):
    """调用方停止等待，任务可能仍在服务端执行。"""


class QueryRetryExhaustedError(ImgApiError):
    """查询连续失败次数过多，但原任务仍可稍后继续查询。"""


@dataclass(frozen=True, slots=True)
class SubmissionResult:
    task_id: str | None
    status: str
    image_urls: tuple[str, ...]
    raw: Mapping[str, Any]

    @property
    def image_url(self) -> str | None:
        return self.image_urls[0] if self.image_urls else None

    @property
    def image(self) -> str | None:
        """兼容旧调用名称。"""
        return self.image_url

    @property
    def is_complete(self) -> bool:
        return self.status in SUCCEEDED_STATUSES and bool(self.image_urls)


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    task_id: str
    status: str
    image_urls: tuple[str, ...]
    raw: Mapping[str, Any]

    @property
    def image_url(self) -> str | None:
        return self.image_urls[0] if self.image_urls else None

    @property
    def image(self) -> str | None:
        """兼容旧调用名称。"""
        return self.image_url


@dataclass(frozen=True, slots=True)
class GenerationResult:
    task_id: str | None
    status: str
    image_urls: tuple[str, ...]
    attempts: int
    elapsed_seconds: float
    raw: Mapping[str, Any]

    @property
    def image_url(self) -> str:
        if not self.image_urls:
            raise ProtocolError("生成结果中没有图片地址", task_id=self.task_id)
        return self.image_urls[0]

    @property
    def image(self) -> str:
        """兼容旧调用名称。"""
        return self.image_url


@dataclass(frozen=True, slots=True)
class _ValidatedOptions:
    model: str
    prompt: str
    aspect_ratio: str
    quality: str
    resolution: str
    urls: tuple[str, ...]
    files: tuple[Path, ...]


class ImgApiClient:
    """
    imgAPI 同步客户端。

    推荐将一个实例复用于多个请求，以复用 TCP/TLS 连接。
    若传入外部 http_client，本类不会替调用方关闭它。
    """

    def __init__(
        self,
        card_key: str | None = None,
        *,
        http_client: httpx.Client | None = None,
        submit_timeout: httpx.Timeout | float | None = None,
        query_timeout: httpx.Timeout | float | None = None,
        poll_initial_interval: float = 2.0,
        poll_max_interval: float = 8.0,
        poll_backoff_factor: float = 1.35,
        poll_jitter_ratio: float = 0.15,
        max_consecutive_query_errors: int = 30,
        max_retry_after_seconds: float = 60.0,
        sleep_func: Callable[[float], None] = time.sleep,
        monotonic_func: Callable[[], float] = time.monotonic,
        random_func: Callable[[], float] = random.random,
        sleep_fn: Callable[[float], None] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        random_fn: Callable[[], float] | None = None,
    ) -> None:
        resolved_key = card_key or os.getenv("IMGAPI_CARD_KEY") or ""
        if not re.fullmatch(r"[0-9a-fA-F]{16}", resolved_key):
            raise ValidationError(
                "IMGAPI_CARD_KEY 必须是 16 位十六进制字符串，且只能保存在服务端环境变量中"
            )

        if poll_initial_interval < 0:
            raise ValidationError("poll_initial_interval 不能小于 0")
        if poll_max_interval < poll_initial_interval:
            raise ValidationError("poll_max_interval 不能小于 poll_initial_interval")
        if poll_backoff_factor < 1:
            raise ValidationError("poll_backoff_factor 不能小于 1")
        if not 0 <= poll_jitter_ratio <= 1:
            raise ValidationError("poll_jitter_ratio 必须在 0 到 1 之间")
        if max_consecutive_query_errors < 1:
            raise ValidationError("max_consecutive_query_errors 必须大于 0")
        if max_retry_after_seconds < 0:
            raise ValidationError("max_retry_after_seconds 不能小于 0")

        self._card_key = resolved_key
        self._submit_timeout = submit_timeout or httpx.Timeout(
            connect=15.0,
            read=60.0,
            write=120.0,
            pool=10.0,
        )
        self._query_timeout = query_timeout or httpx.Timeout(
            connect=10.0,
            read=15.0,
            write=15.0,
            pool=10.0,
        )
        self._poll_initial_interval = float(poll_initial_interval)
        self._poll_max_interval = float(poll_max_interval)
        self._poll_backoff_factor = float(poll_backoff_factor)
        self._poll_jitter_ratio = float(poll_jitter_ratio)
        self._max_consecutive_query_errors = int(max_consecutive_query_errors)
        self._max_retry_after_seconds = float(max_retry_after_seconds)
        # *_fn 是上一版代码使用的参数名，继续兼容，避免替换客户端后改动调用方。
        self._sleep = sleep_fn or sleep_func
        self._monotonic = monotonic_fn or monotonic_func
        self._random = random_fn or random_func

        self._owns_http_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=API_BASE,
            headers={
                "Accept": "application/json",
                "User-Agent": "imgapi-python-client/1.0",
            },
            follow_redirects=False,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            ),
            timeout=self._query_timeout,
        )
        self._closed = False

    def __enter__(self) -> "ImgApiClient":
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        if self._owns_http_client:
            self._client.close()
        self._closed = True

    def submit_image_task(
        self,
        options: Mapping[str, Any] | None = None,
        *,
        model: str | None = None,
        prompt: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        resolution: str | None = None,
        urls: Sequence[str] | None = None,
        files: Sequence[PathInput] | None = None,
        on_task_created: TaskCreatedCallback | None = None,
        **legacy_options: Any,
    ) -> SubmissionResult:
        """
        提交一次生成任务，不自动重试。

        为兼容接口原字段名，也接受 aspectRatio 关键字，但不能同时传
        aspect_ratio 和 aspectRatio 两个不同值。
        """
        self._ensure_open()
        merged = self._merge_generate_options(
            options,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            resolution=resolution,
            urls=urls,
            files=files,
            legacy_options=legacy_options,
        )
        options = self._validate_options(
            model=merged["model"],
            prompt=merged["prompt"],
            aspect_ratio=merged["aspect_ratio"],
            quality=merged["quality"],
            resolution=merged["resolution"],
            urls=merged["urls"],
            files=merged["files"],
        )

        fields = {
            "key": self._card_key,
            "model": options.model,
            "prompt": options.prompt,
            "aspectRatio": options.aspect_ratio,
            "quality": options.quality,
            "resolution": options.resolution,
        }

        try:
            if options.files:
                response = self._submit_multipart(fields, options.urls, options.files)
            else:
                response = self._client.post(
                    f"{API_BASE}{GENERATE_PATH}",
                    json={**fields, "urls": list(options.urls)},
                    timeout=self._submit_timeout,
                    follow_redirects=False,
                )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            # 尚未建立可用连接，通常可以确认请求未送达应用服务器。
            raise TransportError(
                f"提交任务时无法建立连接：{self._safe_exception_text(exc)}",
                submission_uncertain=False,
                definitely_not_sent=True,
            ) from exc
        except httpx.TransportError as exc:
            # 写入中断、读取响应超时等情况下，服务端可能已经收到请求。
            raise SubmissionUncertainError(
                "提交结果不确定：服务端可能已经创建任务。禁止自动重新提交；"
                f"请先检查后台任务或调用记录。底层错误：{self._safe_exception_text(exc)}",
                submission_uncertain=True,
            ) from exc

        try:
            payload = self._decode_response(response)
        except ProtocolError as exc:
            # 已收到 HTTP 成功响应，但无法确认是否已经创建任务，仍需按结果不确定处理。
            raise SubmissionUncertainError(
                "提交接口返回了无法识别的成功响应，服务端可能已经创建任务。"
                "禁止自动重新提交，请先检查后台任务或调用记录。",
                status=exc.status,
                code=exc.code,
                payload=exc.payload,
                submission_uncertain=True,
            ) from exc
        except ApiResponseError as exc:
            if (
                self._numeric_status(exc.status) in AMBIGUOUS_SUBMISSION_HTTP_STATUSES
                or self._numeric_status(exc.code) in AMBIGUOUS_SUBMISSION_HTTP_STATUSES
            ):
                raise SubmissionUncertainError(
                    "提交接口返回了可能存在歧义的网关/服务器错误。服务端可能已经创建任务，"
                    "禁止自动重新提交，请先检查任务记录。",
                    status=exc.status,
                    code=exc.code,
                    retry_after_ms=exc.retry_after_ms,
                    payload=exc.payload,
                    task_id=self._extract_task_id(exc.payload),
                    submission_uncertain=True,
                ) from exc
            raise

        status = self._normalize_status(payload.get("status"))
        task_id = self._extract_task_id(payload)
        image_urls = self._extract_image_urls(payload)

        if status in FAILED_STATUSES:
            raise TaskFailedError(
                self._failure_message(payload, "生成任务提交失败"),
                status=response.status_code,
                code=payload.get("code"),
                payload=payload,
                task_id=task_id,
            )

        if status in SUCCEEDED_STATUSES or (not status and image_urls):
            if not image_urls:
                raise ProtocolError(
                    "提交接口返回成功状态，但没有返回图片地址",
                    status=response.status_code,
                    code=payload.get("code"),
                    payload=payload,
                    task_id=task_id,
                )
            result = SubmissionResult(
                task_id=task_id,
                status="succeeded",
                image_urls=image_urls,
                raw=payload,
            )
            if task_id:
                self._run_task_created_callback(on_task_created, task_id, payload)
            return result

        if not task_id:
            raise ProtocolError(
                "提交接口未返回任务 ID",
                status=response.status_code,
                code=payload.get("code"),
                payload=payload,
            )

        if status and status not in PENDING_STATUSES:
            raise ProtocolError(
                f"提交接口返回了未知任务状态：{status}",
                status=response.status_code,
                code=payload.get("code"),
                payload=payload,
                task_id=task_id,
            )

        result = SubmissionResult(
            task_id=task_id,
            status=status or "submitted",
            image_urls=(),
            raw=payload,
        )
        self._run_task_created_callback(on_task_created, task_id, payload)
        return result

    def query_image_task(self, task_id: str) -> TaskSnapshot:
        """查询一个已存在的任务；此方法不会创建新任务。"""
        self._ensure_open()
        normalized_task_id = self._validate_task_id(task_id)

        try:
            response = self._client.post(
                f"{API_BASE}{QUERY_PATH}",
                json={"key": self._card_key, "id": normalized_task_id},
                timeout=self._query_timeout,
                follow_redirects=False,
            )
        except httpx.TransportError as exc:
            raise TransportError(
                f"查询任务时发生网络错误：{self._safe_exception_text(exc)}",
                task_id=normalized_task_id,
            ) from exc

        try:
            payload = self._decode_response(response)
        except ImgApiError as exc:
            exc.task_id = normalized_task_id
            raise

        status = self._normalize_status(payload.get("status"))
        image_urls = self._extract_image_urls(payload)

        if not status and image_urls:
            status = "succeeded"
        if not status:
            raise ProtocolError(
                "查询接口没有返回任务状态",
                status=response.status_code,
                code=payload.get("code"),
                payload=payload,
                task_id=normalized_task_id,
            )

        if status in SUCCEEDED_STATUSES:
            if not image_urls:
                raise ProtocolError(
                    "任务已成功，但查询接口缺少 image 图片地址",
                    status=response.status_code,
                    code=payload.get("code"),
                    payload=payload,
                    task_id=normalized_task_id,
                )
            status = "succeeded"
        elif status in FAILED_STATUSES:
            status = "failed" if status not in {"refunded"} else "refunded"
        elif status in PENDING_STATUSES:
            # 保留官方返回的 pending 状态，方便上层展示。
            pass
        else:
            raise ProtocolError(
                f"查询接口返回了未知任务状态：{status}",
                status=response.status_code,
                code=payload.get("code"),
                payload=payload,
                task_id=normalized_task_id,
            )

        return TaskSnapshot(
            task_id=normalized_task_id,
            status=status,
            image_urls=image_urls,
            raw=payload,
        )

    def wait_for_image_task(
        self,
        task_id: str,
        *,
        max_poll_duration: float | None = None,
        max_poll_attempts: int = DEFAULT_MAX_POLL_ATTEMPTS,
        on_status: StatusCallback | None = None,
        should_cancel: CancelCallback | None = None,
        max_poll_duration_seconds: float | None = None,
        initial_poll_interval_seconds: float | None = None,
        max_poll_interval_seconds: float | None = None,
    ) -> GenerationResult:
        """使用原 task_id 轮询，适合恢复进程重启前保存的任务。"""
        self._ensure_open()
        normalized_task_id = self._validate_task_id(task_id)
        if max_poll_duration is not None and max_poll_duration_seconds is not None:
            if float(max_poll_duration) != float(max_poll_duration_seconds):
                raise ValidationError(
                    "max_poll_duration 与 max_poll_duration_seconds 不能同时传入不同值"
                )
        selected_duration = (
            max_poll_duration_seconds
            if max_poll_duration_seconds is not None
            else max_poll_duration
        )
        if selected_duration is None:
            selected_duration = DEFAULT_POLL_DURATION_SECONDS

        initial_interval = (
            self._poll_initial_interval
            if initial_poll_interval_seconds is None
            else self._validate_non_negative_finite(
                initial_poll_interval_seconds,
                "initial_poll_interval_seconds",
            )
        )
        maximum_interval = (
            self._poll_max_interval
            if max_poll_interval_seconds is None
            else self._validate_non_negative_finite(
                max_poll_interval_seconds,
                "max_poll_interval_seconds",
            )
        )
        if maximum_interval < initial_interval:
            raise ValidationError(
                "max_poll_interval_seconds 不能小于 initial_poll_interval_seconds"
            )

        duration, attempts_limit = self._validate_poll_limits(
            selected_duration,
            max_poll_attempts,
        )

        started_at = self._monotonic()
        deadline = started_at + duration
        attempts = 0
        consecutive_query_errors = 0
        retry_after_ms = 0

        while attempts < attempts_limit:
            self._raise_if_cancelled(normalized_task_id, should_cancel)
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break

            delay = self._next_poll_delay(
                attempt_index=attempts,
                retry_after_ms=retry_after_ms,
                initial_interval=initial_interval,
                maximum_interval=maximum_interval,
            )
            if delay > 0:
                self._sleep(min(delay, remaining))

            self._raise_if_cancelled(normalized_task_id, should_cancel)
            if deadline - self._monotonic() <= 0:
                break

            attempts += 1
            retry_after_ms = 0

            try:
                snapshot = self.query_image_task(normalized_task_id)
            except ApiResponseError as exc:
                failed_status = self._normalize_status(exc.payload.get("status"))
                if failed_status in FAILED_STATUSES:
                    raise TaskFailedError(
                        self._failure_message(exc.payload, "生成失败"),
                        status=exc.status,
                        code=exc.code,
                        payload=exc.payload,
                        task_id=normalized_task_id,
                    ) from exc

                if self._is_retryable_query_error(exc):
                    consecutive_query_errors += 1
                    retry_after_ms = exc.retry_after_ms
                    self._raise_if_query_errors_exhausted(
                        normalized_task_id,
                        consecutive_query_errors,
                        exc,
                    )
                    continue
                exc.task_id = normalized_task_id
                raise
            except TransportError as exc:
                consecutive_query_errors += 1
                self._raise_if_query_errors_exhausted(
                    normalized_task_id,
                    consecutive_query_errors,
                    exc,
                )
                continue

            consecutive_query_errors = 0
            self._run_status_callback(on_status, snapshot)

            if snapshot.status == "succeeded":
                return GenerationResult(
                    task_id=normalized_task_id,
                    status="succeeded",
                    image_urls=snapshot.image_urls,
                    attempts=attempts,
                    elapsed_seconds=max(0.0, self._monotonic() - started_at),
                    raw=snapshot.raw,
                )

            if snapshot.status in {"failed", "refunded"}:
                raise TaskFailedError(
                    self._failure_message(snapshot.raw, "生成失败"),
                    code=snapshot.raw.get("code"),
                    payload=snapshot.raw,
                    task_id=normalized_task_id,
                )

        elapsed = max(0.0, self._monotonic() - started_at)
        raise PollTimeoutError(
            f"轮询已停止（耗时 {elapsed:.1f} 秒、查询 {attempts} 次）。"
            f"任务可能仍在生成，请保留任务 ID {normalized_task_id}，稍后继续查询。",
            task_id=normalized_task_id,
        )

    def generate_image(
        self,
        options: Mapping[str, Any] | None = None,
        *,
        model: str | None = None,
        prompt: str | None = None,
        aspect_ratio: str | None = None,
        quality: str | None = None,
        resolution: str | None = None,
        urls: Sequence[str] | None = None,
        files: Sequence[PathInput] | None = None,
        on_task_created: TaskCreatedCallback | None = None,
        on_status: StatusCallback | None = None,
        should_cancel: CancelCallback | None = None,
        max_poll_duration: float | None = None,
        max_poll_attempts: int = DEFAULT_MAX_POLL_ATTEMPTS,
        max_poll_duration_seconds: float | None = None,
        initial_poll_interval_seconds: float | None = None,
        max_poll_interval_seconds: float | None = None,
        **legacy_options: Any,
    ) -> GenerationResult:
        """提交一次任务并等待完成；提交阶段永不自动重试。"""
        started_at = self._monotonic()
        merged = self._merge_generate_options(
            options,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            quality=quality,
            resolution=resolution,
            urls=urls,
            files=files,
            legacy_options=legacy_options,
        )

        submitted = self.submit_image_task(
            merged,
            on_task_created=on_task_created,
        )

        if submitted.is_complete:
            return GenerationResult(
                task_id=submitted.task_id,
                status="succeeded",
                image_urls=submitted.image_urls,
                attempts=0,
                elapsed_seconds=max(0.0, self._monotonic() - started_at),
                raw=submitted.raw,
            )

        if not submitted.task_id:
            raise ProtocolError("任务未完成且没有 task_id", payload=submitted.raw)

        result = self.wait_for_image_task(
            submitted.task_id,
            max_poll_duration=max_poll_duration,
            max_poll_attempts=max_poll_attempts,
            on_status=on_status,
            should_cancel=should_cancel,
            max_poll_duration_seconds=max_poll_duration_seconds,
            initial_poll_interval_seconds=initial_poll_interval_seconds,
            max_poll_interval_seconds=max_poll_interval_seconds,
        )
        return GenerationResult(
            task_id=result.task_id,
            status=result.status,
            image_urls=result.image_urls,
            attempts=result.attempts,
            elapsed_seconds=max(0.0, self._monotonic() - started_at),
            raw=result.raw,
        )

    def _submit_multipart(
        self,
        fields: Mapping[str, str],
        urls: tuple[str, ...],
        paths: tuple[Path, ...],
    ) -> httpx.Response:
        with ExitStack() as stack:
            multipart_files: list[tuple[str, tuple[str, Any, str]]] = []
            for path in paths:
                handle = stack.enter_context(path.open("rb"))
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                multipart_files.append(
                    (
                        "files",
                        (self._safe_filename(path.name), handle, content_type),
                    )
                )

            form_data: dict[str, Any] = dict(fields)
            if urls:
                # HTTPX 会把列表编码成多个同名 form-data 字段。
                form_data["urls"] = list(urls)

            return self._client.post(
                f"{API_BASE}{GENERATE_PATH}",
                data=form_data,
                files=multipart_files,
                timeout=self._submit_timeout,
                follow_redirects=False,
            )

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        retry_after_ms = self._parse_retry_after_ms(
            response.headers.get("Retry-After", ""),
            None,
        )

        try:
            decoded = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            preview = self._safe_response_preview(response.content)
            if 200 <= response.status_code < 300:
                raise ProtocolError(
                    f"接口返回的不是有效 JSON：{preview}",
                    status=response.status_code,
                ) from exc
            raise ApiResponseError(
                f"请求失败（HTTP {response.status_code}），且响应不是有效 JSON：{preview}",
                status=response.status_code,
                retry_after_ms=retry_after_ms,
            ) from exc

        if not isinstance(decoded, Mapping):
            if 200 <= response.status_code < 300:
                raise ProtocolError(
                    "接口 JSON 响应必须是对象",
                    status=response.status_code,
                )
            raise ApiResponseError(
                f"请求失败（HTTP {response.status_code}）",
                status=response.status_code,
                retry_after_ms=retry_after_ms,
            )

        envelope = dict(decoded)
        wrapped = envelope.get("data")
        normalized = dict(envelope)
        if isinstance(wrapped, Mapping):
            normalized.update(wrapped)

        retry_after_ms = self._parse_retry_after_ms(
            response.headers.get("Retry-After", ""),
            normalized.get("retryAfterMs"),
        )

        code = normalized.get("code")
        business_failed = "code" in normalized and not self._is_success_code(code)
        failed = (
            not 200 <= response.status_code < 300
            or normalized.get("ok") is False
            or business_failed
        )

        safe_payload = self._redact_payload(normalized)
        if failed:
            message = self._failure_message(
                safe_payload,
                f"请求失败（HTTP {response.status_code}）",
            )
            raise ApiResponseError(
                message,
                status=response.status_code,
                code=code,
                retry_after_ms=retry_after_ms,
                payload=safe_payload,
            )

        return safe_payload

    def _validate_options(
        self,
        *,
        model: str,
        prompt: str,
        aspect_ratio: str,
        quality: str,
        resolution: str,
        urls: Sequence[str] | None,
        files: Sequence[PathInput] | None,
    ) -> _ValidatedOptions:
        if model not in SUPPORTED_MODELS:
            allowed = "、".join(sorted(SUPPORTED_MODELS))
            raise ValidationError(f"model 只支持：{allowed}")

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationError("prompt 必须是非空字符串")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValidationError(f"prompt 最多 {MAX_PROMPT_LENGTH} 个字符")

        if not isinstance(aspect_ratio, str) or not aspect_ratio.strip():
            raise ValidationError("aspectRatio 必须是非空字符串")
        normalized_ratio = aspect_ratio.strip()
        if normalized_ratio != "auto" and not re.fullmatch(
            r"[1-9]\d{0,2}:[1-9]\d{0,2}",
            normalized_ratio,
        ):
            raise ValidationError("aspectRatio 必须是 auto 或类似 1:1、16:9 的比例")

        if quality in {"xhigh", "max"} and model != "gpt-image-2.5-sunburst":
            raise ValidationError("xhigh、max 仅支持 gpt-image-2.5-sunburst")
        if quality not in SUPPORTED_QUALITIES:
            allowed = "、".join(sorted(SUPPORTED_QUALITIES))
            raise ValidationError(f"quality 只支持：{allowed}")
        if resolution not in SUPPORTED_RESOLUTIONS:
            allowed = "、".join(sorted(SUPPORTED_RESOLUTIONS))
            raise ValidationError(f"resolution 只支持：{allowed}")

        normalized_urls = self._normalize_urls(urls)
        normalized_files = self._normalize_files(files)
        if len(normalized_urls) + len(normalized_files) > MAX_REFERENCE_IMAGES:
            raise ValidationError(
                f"urls 和 files 合计最多 {MAX_REFERENCE_IMAGES} 张参考图"
            )

        return _ValidatedOptions(
            model=model,
            prompt=prompt,
            aspect_ratio=normalized_ratio,
            quality=quality,
            resolution=resolution,
            urls=normalized_urls,
            files=normalized_files,
        )

    def _normalize_urls(self, urls: Sequence[str] | None) -> tuple[str, ...]:
        values = self._normalize_sequence(urls, "urls")
        normalized: list[str] = []
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"urls[{index}] 必须是非空字符串")
            url = value.strip()
            parsed = urlsplit(url)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                raise ValidationError(f"urls[{index}] 必须是完整的 HTTPS 图片地址")
            if parsed.username or parsed.password:
                raise ValidationError(f"urls[{index}] 不允许在 URL 中携带用户名或密码")
            normalized.append(url)
        return tuple(normalized)

    def _normalize_files(self, files: Sequence[PathInput] | None) -> tuple[Path, ...]:
        values = self._normalize_sequence(files, "files")
        normalized: list[Path] = []
        for index, value in enumerate(values):
            if not isinstance(value, (str, os.PathLike)):
                raise ValidationError(f"files[{index}] 必须是本地文件路径")
            path = Path(value).expanduser()
            if not path.exists():
                raise ValidationError(f"files[{index}] 不存在：{path}")
            if not path.is_file():
                raise ValidationError(f"files[{index}] 不是普通文件：{path}")
            try:
                with path.open("rb"):
                    pass
            except OSError as exc:
                raise ValidationError(f"files[{index}] 无法读取：{path}") from exc
            normalized.append(path)
        return tuple(normalized)

    @staticmethod
    def _normalize_sequence(value: Any, field_name: str) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, bytearray, os.PathLike, Mapping)):
            raise ValidationError(f"{field_name} 必须是列表，不能直接传字符串或对象")
        try:
            return list(value)
        except TypeError as exc:
            raise ValidationError(f"{field_name} 必须是列表") from exc

    @staticmethod
    def _validate_task_id(task_id: str) -> str:
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValidationError("task_id 必须是非空字符串")
        normalized = task_id.strip()
        if len(normalized) > 512:
            raise ValidationError("task_id 长度异常")
        return normalized

    @staticmethod
    def _validate_poll_limits(duration: float, attempts: int) -> tuple[float, int]:
        try:
            normalized_duration = float(duration)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("max_poll_duration 必须是有效数字") from exc
        if not math.isfinite(normalized_duration) or normalized_duration <= 0:
            raise ValidationError("max_poll_duration 必须大于 0")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts <= 0:
            raise ValidationError("max_poll_attempts 必须是大于 0 的整数")
        return normalized_duration, attempts

    def _next_poll_delay(
        self,
        *,
        attempt_index: int,
        retry_after_ms: int,
        initial_interval: float,
        maximum_interval: float,
    ) -> float:
        if retry_after_ms > 0:
            return min(retry_after_ms / 1000.0, self._max_retry_after_seconds)

        base = min(
            initial_interval * (self._poll_backoff_factor ** attempt_index),
            maximum_interval,
        )
        if base <= 0 or self._poll_jitter_ratio <= 0:
            return max(0.0, base)

        random_value = min(1.0, max(0.0, float(self._random())))
        jitter_factor = 1.0 + ((2.0 * random_value - 1.0) * self._poll_jitter_ratio)
        return max(0.0, base * jitter_factor)

    def _is_retryable_query_error(self, exc: ApiResponseError) -> bool:
        status = self._numeric_status(exc.status)
        code = self._numeric_status(exc.code)
        return (
            status in RETRYABLE_QUERY_HTTP_STATUSES
            or code in RETRYABLE_QUERY_HTTP_STATUSES
        )

    def _raise_if_query_errors_exhausted(
        self,
        task_id: str,
        consecutive_errors: int,
        last_error: ImgApiError,
    ) -> None:
        if consecutive_errors < self._max_consecutive_query_errors:
            return
        raise QueryRetryExhaustedError(
            f"查询任务连续失败 {consecutive_errors} 次。请保留任务 ID {task_id}，稍后继续查询。"
            f"最后错误：{last_error}",
            status=last_error.status,
            code=last_error.code,
            retry_after_ms=last_error.retry_after_ms,
            payload=last_error.payload,
            task_id=task_id,
        ) from last_error

    def _raise_if_cancelled(
        self,
        task_id: str,
        should_cancel: CancelCallback | None,
    ) -> None:
        if should_cancel is None:
            return
        try:
            cancelled = bool(should_cancel())
        except Exception as exc:
            raise TaskCallbackError(
                f"取消检查回调执行失败：{exc}",
                task_id=task_id,
            ) from exc
        if cancelled:
            raise PollCancelledError(
                f"已停止等待。服务端任务可能仍在运行，请保留任务 ID {task_id}。",
                task_id=task_id,
            )

    @staticmethod
    def _run_task_created_callback(
        callback: TaskCreatedCallback | None,
        task_id: str,
        raw: Mapping[str, Any],
    ) -> None:
        if callback is None:
            return
        try:
            # 新版回调可接收 (task_id, raw)，同时兼容旧版只接收 task_id。
            try:
                signature = inspect.signature(callback)
            except (TypeError, ValueError):
                callback(task_id, dict(raw))
            else:
                try:
                    signature.bind(task_id, raw)
                except TypeError:
                    signature.bind(task_id)
                    callback(task_id)
                else:
                    callback(task_id, dict(raw))
        except Exception as exc:
            raise TaskPersistenceError(
                "服务端已经创建任务，但保存任务 ID 失败。禁止重新提交；"
                f"请立即保存任务 ID {task_id} 并稍后恢复查询。原始错误：{exc}",
                task_id=task_id,
            ) from exc

    @staticmethod
    def _validate_non_negative_finite(value: Any, field_name: str) -> float:
        try:
            normalized = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError(f"{field_name} 必须是有效数字") from exc
        if not math.isfinite(normalized) or normalized < 0:
            raise ValidationError(f"{field_name} 必须是大于或等于 0 的有限数字")
        return normalized

    @staticmethod
    def _merge_generate_options(
        options: Mapping[str, Any] | None,
        *,
        model: str | None,
        prompt: str | None,
        aspect_ratio: str | None,
        quality: str | None,
        resolution: str | None,
        urls: Sequence[str] | None,
        files: Sequence[PathInput] | None,
        legacy_options: Mapping[str, Any],
    ) -> dict[str, Any]:
        if options is None:
            merged: dict[str, Any] = {}
        elif isinstance(options, Mapping):
            merged = dict(options)
        else:
            raise ValidationError("options 必须是字典")

        extra = dict(legacy_options)
        for key, value in extra.items():
            if key in merged and merged[key] != value:
                raise ValidationError(f"参数 {key} 被重复传入且值不同")
            merged[key] = value

        explicit = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "quality": quality,
            "resolution": resolution,
            "urls": urls,
            "files": files,
        }
        for key, value in explicit.items():
            if value is None:
                continue
            if key in merged and merged[key] != value:
                raise ValidationError(f"参数 {key} 被重复传入且值不同")
            merged[key] = value

        if "aspectRatio" in merged:
            legacy_ratio = merged.pop("aspectRatio")
            if "aspect_ratio" in merged and merged["aspect_ratio"] != legacy_ratio:
                raise ValidationError("aspect_ratio 与 aspectRatio 不能同时传入不同值")
            merged["aspect_ratio"] = legacy_ratio

        allowed = {
            "model",
            "prompt",
            "aspect_ratio",
            "quality",
            "resolution",
            "urls",
            "files",
        }
        unknown = sorted(set(merged) - allowed)
        if unknown:
            raise ValidationError(f"存在不支持的参数：{'、'.join(unknown)}")

        return {
            "model": merged.get("model"),
            "prompt": merged.get("prompt"),
            "aspect_ratio": merged.get("aspect_ratio", "auto"),
            "quality": merged.get("quality", "auto"),
            "resolution": merged.get("resolution", "1K"),
            "urls": merged.get("urls"),
            "files": merged.get("files"),
        }

    @staticmethod
    def _run_status_callback(
        callback: StatusCallback | None,
        snapshot: TaskSnapshot,
    ) -> None:
        if callback is None:
            return
        try:
            callback(snapshot)
        except Exception as exc:
            raise TaskCallbackError(
                f"任务状态回调执行失败：{exc}。请保留任务 ID {snapshot.task_id}。",
                task_id=snapshot.task_id,
            ) from exc

    @staticmethod
    def _resolve_aspect_ratio(aspect_ratio: str, legacy_options: dict[str, Any]) -> str:
        if "aspectRatio" not in legacy_options:
            return aspect_ratio
        legacy_value = legacy_options.pop("aspectRatio")
        if aspect_ratio != "auto" and legacy_value != aspect_ratio:
            raise ValidationError("aspect_ratio 与 aspectRatio 不能同时传入不同值")
        return legacy_value

    @staticmethod
    def _reject_unknown_options(options: Mapping[str, Any]) -> None:
        if options:
            names = "、".join(sorted(options))
            raise ValidationError(f"存在不支持的参数：{names}")

    def _parse_retry_after_ms(self, header_value: str, body_value: Any) -> int:
        try:
            milliseconds = float(body_value or 0)
            if math.isfinite(milliseconds) and milliseconds > 0:
                return int(milliseconds)
        except (TypeError, ValueError, OverflowError):
            pass

        text = str(header_value or "").strip()
        if not text:
            return 0
        try:
            seconds = float(text)
            if math.isfinite(seconds):
                return max(0, int(seconds * 1000))
            return 0
        except (TypeError, ValueError, OverflowError):
            pass

        try:
            moment = parsedate_to_datetime(text)
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            delta = (moment - datetime.now(timezone.utc)).total_seconds()
            if not math.isfinite(delta):
                return 0
            return max(0, int(delta * 1000))
        except (TypeError, ValueError, OverflowError):
            return 0

    @staticmethod
    def _normalize_status(value: Any) -> str:
        return str(value or "").strip().lower()

    @staticmethod
    def _extract_task_id(payload: Mapping[str, Any]) -> str | None:
        for name in ("id", "task_id", "taskId"):
            value = payload.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _extract_image_urls(payload: Mapping[str, Any]) -> tuple[str, ...]:
        candidates: list[Any] = []
        for name in ("image", "images", "image_url", "imageUrl"):
            if name in payload:
                candidates.append(payload[name])

        results: list[str] = []

        def add(value: Any) -> None:
            if isinstance(value, str):
                text = value.strip()
                if text and text not in results:
                    results.append(text)
                return
            if isinstance(value, Mapping):
                for key in ("url", "image", "image_url", "imageUrl"):
                    if key in value:
                        add(value[key])
                return
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    add(item)

        for candidate in candidates:
            add(candidate)
        return tuple(results)

    def _redact_payload(self, value: Mapping[str, Any]) -> dict[str, Any]:
        def redact(item: Any, key_name: str = "") -> Any:
            lowered = key_name.lower().replace("_", "")
            if lowered in {"key", "cardkey", "apikey", "authorization"}:
                return "***REDACTED***"
            if isinstance(item, Mapping):
                return {str(key): redact(val, str(key)) for key, val in item.items()}
            if isinstance(item, list):
                return [redact(entry) for entry in item]
            if isinstance(item, tuple):
                return tuple(redact(entry) for entry in item)
            if isinstance(item, str) and self._card_key in item:
                return item.replace(self._card_key, "***REDACTED***")
            return item

        result = redact(value)
        return dict(result) if isinstance(result, Mapping) else {}

    @staticmethod
    def _failure_message(payload: Mapping[str, Any], fallback: str) -> str:
        for name in ("error", "msg", "message", "failure_reason"):
            value = payload.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return fallback

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = str(name).replace('"', "_").replace("\r", "_").replace("\n", "_")
        cleaned = cleaned.replace("/", "_").replace("\\", "_")
        return cleaned or "reference-image"

    def _safe_exception_text(self, exc: BaseException) -> str:
        text = str(exc) or exc.__class__.__name__
        return text.replace(self._card_key, "***REDACTED***")

    def _safe_response_preview(self, raw: bytes, limit: int = 300) -> str:
        preview = raw[:limit].decode("utf-8", errors="replace")
        preview = preview.replace(self._card_key, "***REDACTED***")
        suffix = "…" if len(raw) > limit else ""
        return repr(preview + suffix)

    @staticmethod
    def _is_success_code(code: Any) -> bool:
        try:
            return int(code) == 200
        except (TypeError, ValueError, OverflowError):
            return False

    @staticmethod
    def _numeric_status(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return 0

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("ImgApiClient 已关闭")


def generate_image(
    options: Mapping[str, Any],
    *,
    card_key: str | None = None,
    on_task_created: TaskCreatedCallback | None = None,
    on_status: StatusCallback | None = None,
    max_poll_duration_seconds: float = DEFAULT_POLL_DURATION_SECONDS,
) -> str:
    """
    兼容原脚本的单函数用法，返回第一张图片 URL。

    正式网站建议自行持有并复用 ImgApiClient 实例，不要每张图创建一个连接池。
    """
    with ImgApiClient(card_key=card_key) as client:
        result = client.generate_image(
            options,
            on_task_created=on_task_created,
            on_status=on_status,
            max_poll_duration_seconds=max_poll_duration_seconds,
        )
    return result.image_url


def main() -> None:
    """本地调用示例。正式项目应将 on_task_created 替换为数据库写入。"""

    def save_task_id(task_id: str) -> None:
        # 生产环境：这里应先写数据库，再开始轮询。
        print(f"任务 ID：{task_id}")

    def show_status(snapshot: TaskSnapshot) -> None:
        print(f"任务状态：{snapshot.status}")

    try:
        with ImgApiClient() as client:
            result = client.generate_image(
                model="gpt-image-2",
                prompt="一只戴着墨镜的柴犬坐在沙滩上喝可乐，赛博朋克风格",
                aspect_ratio="1:1",
                quality="auto",
                resolution="1K",
                urls=[],
                files=[],
                on_task_created=save_task_id,
                on_status=show_status,
            )

        print("生成成功：")
        for image_url in result.image_urls:
            print(image_url)
    except SubmissionUncertainError as exc:
        print(f"提交结果不确定：{exc}")
        raise SystemExit(2) from exc
    except ImgApiError as exc:
        print(f"生成失败：{exc}")
        if exc.task_id:
            print(f"请保留任务 ID：{exc.task_id}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
