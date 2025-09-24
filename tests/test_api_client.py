import unittest
from unittest.mock import patch
from requests import Response
from sdk_reforge._requests import ApiClient, CacheEntry
import time


# Dummy options for testing.
class DummyOptions:
    reforge_api_urls = ["https://a.example.com", "https://b.example.com"]
    version = "1.0"


class TestApiClient(unittest.TestCase):
    def setUp(self):
        self.options = DummyOptions()
        self.client = ApiClient(self.options)
        # Instead of setting statistics on resilient_request,
        # patch _get_attempt_number to always return 1.
        self.client._get_attempt_number = lambda: 1

    def create_response(
        self,
        status_code=200,
        content=b"dummy",
        headers=None,
        url="https://a.example.com/api/v1/configs/0",
    ):
        resp = Response()
        resp.status_code = status_code
        resp._content = content
        resp.url = url
        resp.headers = headers or {}
        return resp

    @patch.object(ApiClient, "_send_request")
    def test_no_cache(self, mock_send_request):
        # Test that when allow_cache is False, caching is bypassed.
        response = self.create_response(
            status_code=200,
            content=b"response_no_cache",
            headers={"Cache-Control": "max-age=60", "ETag": "abc"},
            url="https://a.example.com/api/v1/configs/0",
        )
        mock_send_request.return_value = response

        resp = self.client.resilient_request("/api/v1/configs/0", allow_cache=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"response_no_cache")
        self.assertNotIn("X-Cache", resp.headers)

    @patch.object(ApiClient, "_send_request")
    def test_cache_miss_and_hit(self, mock_send_request):
        # First call should cache the response (MISS).
        response = self.create_response(
            status_code=200,
            content=b"cached_response",
            headers={"Cache-Control": "max-age=60", "ETag": "abc"},
            url="https://a.example.com/api/v1/configs/0",
        )
        mock_send_request.return_value = response

        resp1 = self.client.resilient_request("/api/v1/configs/0", allow_cache=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.content, b"cached_response")
        self.assertEqual(resp1.headers.get("X-Cache"), "MISS")

        # Change the mock so that a new network call would return different content.
        new_response = self.create_response(
            status_code=200,
            content=b"new_response",
            headers={"Cache-Control": "max-age=60", "ETag": "def"},
            url="https://a.example.com/api/v1/configs/0",
        )
        mock_send_request.return_value = new_response

        # Second call should return the cached response.
        resp2 = self.client.resilient_request("/api/v1/configs/0", allow_cache=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.content, b"cached_response")
        self.assertEqual(resp2.headers.get("X-Cache"), "HIT")

    @patch.object(ApiClient, "_send_request")
    def test_304_returns_cached_response(self, mock_send_request):
        # First, cache a 200 response.
        response = self.create_response(
            status_code=200,
            content=b"cached_response",
            headers={"Cache-Control": "max-age=60", "ETag": "abc"},
            url="https://a.example.com/api/v1/configs/0",
        )
        mock_send_request.return_value = response
        resp1 = self.client.resilient_request("/api/v1/configs/0", allow_cache=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.content, b"cached_response")
        self.assertEqual(resp1.headers.get("X-Cache"), "MISS")

        # Now simulate a 304 Not Modified response.
        response_304 = self.create_response(
            status_code=304,
            content=b"",
            headers={},
            url="https://a.example.com/api/v1/configs/0",
        )
        mock_send_request.return_value = response_304
        resp2 = self.client.resilient_request("/api/v1/configs/0", allow_cache=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.content, b"cached_response")
        self.assertEqual(resp2.headers.get("X-Cache"), "HIT")

    @patch.object(ApiClient, "_send_request")
    def test_if_none_match_header_added(self, mock_send_request):
        # Pre-populate the cache with a stale entry.
        # Set the expires_at to a time in the past so that it's considered stale.
        stale_time = time.time() - 10
        cache_url = "https://a.example.com/api/v1/configs/0"
        self.client.cache.set(
            cache_url,
            CacheEntry(
                data=b"old_response",
                etag="abc123",
                expires_at=stale_time,
                url=cache_url,
            ),
        )

        # Prepare a dummy 304 Not Modified response.
        response_304 = self.create_response(
            status_code=304, content=b"", headers={}, url=cache_url
        )
        mock_send_request.return_value = response_304

        # Call resilient_request with caching enabled.
        resp = self.client.resilient_request("/api/v1/configs/0", allow_cache=True)

        # Verify that _send_request was called with an "If-None-Match" header.
        args, kwargs = mock_send_request.call_args
        headers = kwargs.get("headers", {})
        self.assertIn("If-None-Match", headers)
        self.assertEqual(headers["If-None-Match"], "abc123")

        # Also, the response should be synthesized from the cache (a HIT).
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"old_response")
        self.assertEqual(resp.headers.get("X-Cache"), "HIT")


if __name__ == "__main__":
    unittest.main()
