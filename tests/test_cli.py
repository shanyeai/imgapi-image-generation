import contextlib
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import imgapi
import run


class CliTests(unittest.TestCase):
    def cli(self, *args, cwd=ROOT):
        # -S disables site-packages: previews must work even without HTTPX.
        return subprocess.run([sys.executable, "-S", str(ROOT / "python/run.py"), *args],
            cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=10,
            env={**os.environ, "IMGAPI_CARD_KEY": "", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})

    def test_recipes_preview_without_key_or_dependencies(self):
        for name in ("quickstart", "product-photo", "article-cover"):
            result = self.cli("--dry-run", "--request", f"examples/{name}.json")
            self.assertEqual(result.returncode, 0, result.stderr)
            preview = json.loads(result.stdout)
            self.assertEqual(preview["mode"], "dry-run")
            self.assertIs(preview["network"], False)
            self.assertNotIn("key", preview["request"])
            def respond(request):
                self.assertEqual(json.loads(request.content)["prompt"], preview["request"]["prompt"])
                return httpx.Response(200, json={"code": 200, "status": "succeeded", "image": "https://example.com/result.png"})
            with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                with imgapi.ImgApiClient(card_key="0123456789abcdef", http_client=http) as client:
                    client.submit_image_task(preview["request"])

    def test_help_and_default_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.cli("--dry-run", cwd=directory).returncode, 0)
        self.assertEqual(self.cli("--help").returncode, 0)

    def test_reference_recipe_through_entrypoint(self):
        preview = self.cli("--dry-run", "--request", "examples/reference-edit.json")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["contentType"], "multipart/form-data")
        image_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aB9sAAAAASUVORK5CYII=")
        calls = []
        def respond(request):
            calls.append(request)
            self.assertTrue(str(request.url).endswith("/draw/Async"))
            self.assertIn('multipart/form-data', request.headers['Content-Type'])
            self.assertIn(b'filename="reference.png"', request.content)
            self.assertIn(image_bytes, request.content)
            return httpx.Response(200, json={"code": 200, "status": "succeeded", "image": "https://example.com/reference-result.png"})
        original = imgapi.ImgApiClient
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            with patch.object(imgapi, "ImgApiClient", side_effect=lambda: original(card_key="0123456789abcdef", http_client=http)):
                with tempfile.TemporaryDirectory() as directory:
                    previous = Path.cwd()
                    try:
                        os.chdir(directory)
                        Path("reference.png").write_bytes(image_bytes)
                        output = io.StringIO()
                        with patch.object(sys, "argv", ["run.py", "--request", str(ROOT / "examples/reference-edit.json")]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                            run.main()
                        self.assertEqual(len(calls), 1)
                        self.assertIn("reference-result.png", output.getvalue())
                    finally:
                        os.chdir(previous)

    def test_invalid_combinations(self):
        for args in (("--query", "x", "--dry-run"), ("--query", "x", "--request", "x"), ("--query", ""), ("--unknown",)):
            self.assertNotEqual(self.cli(*args).returncode, 0)

    def test_bad_request_does_not_echo_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            for content in ('{"key":"sensitive-placeholder","model":"x","prompt":"x"}', '{"key":"sensitive-placeholder"', '[]', '{"model":"x","prompt":"x","files":null}'):
                path.write_text(content, encoding="utf-8")
                result = self.cli("--dry-run", "--request", str(path))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("sensitive-placeholder", result.stdout + result.stderr)

    def test_entrypoint_persistence_and_recovery(self):
        calls = []
        def respond(request):
            calls.append(request)
            if len(calls) == 1:
                self.assertTrue(str(request.url).endswith("/draw/Async"))
                return httpx.Response(200, json={"code": 200, "status": "submitted", "taskId": "cli-task"})
            self.assertTrue(str(request.url).endswith("/query"))
            self.assertEqual(json.loads(request.content)["id"], "cli-task")
            return httpx.Response(200, json={"code": 200, "status": "succeeded", "image": "https://example.com/result.png"})
        original = imgapi.ImgApiClient
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            with patch.object(imgapi, "ImgApiClient", side_effect=lambda: original(card_key="0123456789abcdef", http_client=http, sleep_func=lambda _: None)):
                with tempfile.TemporaryDirectory() as directory:
                    previous = Path.cwd()
                    try:
                        os.chdir(directory)
                        for args in (["run.py"], ["run.py", "--query", "cli-task"]):
                            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                                run.main()
                        self.assertEqual(Path("task-id.txt").read_text().strip(), "cli-task")
                        self.assertEqual(len(calls), 3)
                    finally:
                        os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
