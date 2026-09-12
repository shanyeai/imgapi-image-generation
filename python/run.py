"""Run from the repository root: python python/run.py [--query TASK_ID]."""
import argparse
import json
import os
import sys
from pathlib import Path


def save_task(task_id):
    print(f"Task ID: {task_id}", flush=True)
    Path("task-id.txt").write_text(task_id + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Without --dry-run or --query, submits ONE billable image task.")
    parser.add_argument("--query", metavar="TASK_ID", help="Resume an existing task; never submit")
    parser.add_argument("--request", metavar="JSON_FILE", help="Load request fields from JSON; no credentials")
    parser.add_argument("--dry-run", action="store_true", help="Print request preview; no Key, dependency or network needed")
    args = parser.parse_args()
    if args.query is not None and (args.dry_run or args.request is not None or not args.query.strip()):
        parser.error("--query requires a task ID and cannot be combined with --request or --dry-run")
    try:
        if args.query is None:
            source = Path(args.request) if args.request is not None else Path(__file__).resolve().parents[1] / "examples/quickstart.json"
            try:
                request = json.loads(source.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raise ValueError("Request file must be readable UTF-8 JSON") from None
            allowed = {"model", "prompt", "aspectRatio", "quality", "resolution", "urls", "files"}
            if not isinstance(request, dict) or set(request) - allowed:
                raise ValueError("Request JSON may only contain model, prompt, aspectRatio, quality, resolution, urls and files; never put credentials in it")
            if any(not isinstance(request.get(field), str) or not request[field].strip() for field in ("model", "prompt")):
                raise ValueError("Request JSON requires non-empty model and prompt strings")
            for field in ("aspectRatio", "quality", "resolution"):
                if field in request and not isinstance(request[field], str):
                    raise ValueError(f"{field} must be a string")
            for field in ("urls", "files"):
                if field in request and (not isinstance(request[field], list) or any(not isinstance(value, str) or not value.strip() for value in request[field])):
                    raise ValueError(f"{field} must be an array of non-empty strings")
            if args.dry_run:
                print(json.dumps({"mode": "dry-run", "network": False,
                    "endpoint": "https://imgapi.vip/prod-api/tool/imgapi/draw/Async",
                    "contentType": "multipart/form-data" if request.get("files") else "application/json",
                    "request": request}, ensure_ascii=False, indent=2))
                return
    except ValueError as exc:
        parser.error(str(exc))

    # --help and --dry-run work before installing third-party dependencies.
    try:
        from imgapi import ImgApiClient, ImgApiError
    except ModuleNotFoundError:
        parser.error("Install dependencies: python -m pip install -r python/requirements.txt")
    try:
        with ImgApiClient() as client:
            if args.query is not None:
                result = client.wait_for_image_task(args.query)
            else:
                print("Submitting ONE billable task. No automatic resubmission.", file=sys.stderr)
                result = client.generate_image(request, on_task_created=save_task)
        print(f"Task ID: {result.task_id}")
        print(result.image_url)
    except (ImgApiError, OSError) as exc:
        key = os.environ.get("IMGAPI_CARD_KEY")
        print(str(exc).replace(key, "[REDACTED]") if key else str(exc))
        if getattr(exc, "task_id", None):
            print(f"Resume with --query {exc.task_id}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
