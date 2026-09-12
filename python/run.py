"""Run from the repository root: python python/run.py [--query TASK_ID]."""
import argparse
import os
from pathlib import Path
from imgapi import ImgApiClient, ImgApiError


def save_task(task_id):
    print(f"Task ID: {task_id}", flush=True)
    Path("task-id.txt").write_text(task_id + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", metavar="TASK_ID", help="Resume an existing task; never submit")
    args = parser.parse_args()
    try:
        with ImgApiClient() as client:
            if args.query is not None:
                result = client.wait_for_image_task(args.query)
            else:
                result = client.generate_image(
                    model="gpt-image-2",
                    prompt="一只戴着墨镜的柴犬坐在沙滩上喝可乐，赛博朋克风格",
                    aspect_ratio="1:1", quality="auto", resolution="1K",
                    urls=[], files=[], on_task_created=save_task,
                )
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
