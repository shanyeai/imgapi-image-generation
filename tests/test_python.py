import json
from pathlib import Path
import sys
import tempfile
import unittest
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from imgapi import ImgApiClient, ImgApiError, SubmissionUncertainError

KEY = "0123456789abcdef"  # Fake fixture; MockTransport prevents network requests.


class ClientTests(unittest.TestCase):
    def client(self, responses):
        self.calls = []
        def respond(request):
            self.calls.append(request)
            self.assertTrue(responses, "Unexpected extra request")
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return httpx.Response(200, json=response)
        transport = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(transport.close)
        client = ImgApiClient(card_key=KEY, http_client=transport, sleep_func=lambda _: None)
        self.addCleanup(client.close)
        return client

    def test_success_and_task_saved_before_poll(self):
        client = self.client([
            {"code": 200, "data": {"task_id": "task-1", "status": "submitted"}},
            {"code": 200, "status": "processing"},
            {"code": 200, "data": {"status": "succeeded", "image": "https://example.com/result.png"}},
        ])
        def saved(task_id):
            self.assertEqual(task_id, "task-1")
            self.assertEqual(len(self.calls), 1)
        result = client.generate_image(model="gpt-image-2", prompt="test", on_task_created=saved)
        self.assertEqual(result.image_url, "https://example.com/result.png")
        self.assertEqual(str(self.calls[0].url), "https://imgapi.vip/prod-api/tool/imgapi/draw/Async")
        for request in self.calls[1:]:
            self.assertEqual(str(request.url), "https://imgapi.vip/prod-api/tool/gptimage2/query")
            self.assertEqual(json.loads(request.content), {"key": KEY, "id": "task-1"})

    def test_uncertain_submit_no_retry(self):
        client = self.client([httpx.ReadTimeout("mock timeout")])
        with self.assertRaises(SubmissionUncertainError):
            client.generate_image(model="gpt-image-2", prompt="test")
        self.assertEqual(len(self.calls), 1)

    def test_resume_refund_only_queries(self):
        client = self.client([{"code": 200, "status": "refunded", "error": "refunded"}])
        with self.assertRaises(ImgApiError) as context:
            client.wait_for_image_task("existing")
        self.assertEqual(context.exception.task_id, "existing")
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(str(self.calls[0].url).endswith("/query"))

    def test_multipart(self):
        client = self.client([{"code": 200, "taskId": "multipart", "status": "submitted"}])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ref.png"
            path.write_bytes(b"mock image")
            client.submit_image_task(model="gpt-image-2", prompt="test", files=[str(path)], urls=["https://example.com/ref.png"])
        request = self.calls[0]
        self.assertIn("multipart/form-data; boundary=", request.headers["Content-Type"])
        self.assertIn(b'name="files"', request.content)
        self.assertIn(b'name="urls"', request.content)

    def test_business_failure_and_invalid_model(self):
        client = self.client([{"code": 500, "msg": "failure"}])
        with self.assertRaises(ImgApiError):
            client.submit_image_task(model="gpt-image-2", prompt="test")
        with self.assertRaises(ImgApiError):
            client.submit_image_task(model="invalid", prompt="test")
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
