import re
from collections import OrderedDict
from dataclasses import dataclass
import time

from ._internal_logging import (
    InternalLogger,
)
import requests
from requests import Response, RequestException
from requests.adapters import HTTPAdapter
from tenacity import (
    retry,
    stop_after_delay,
    wait_exponential,
    retry_if_exception_type,
)

import os

logger = InternalLogger(__name__)


def _get_version():
    try:
        version_file = os.path.join(os.path.dirname(__file__), "VERSION")
        with open(version_file, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, IOError):
        return "development"


Version = _get_version()


VersionHeader = "X-Reforge-SDK-Version"

DEFAULT_TIMEOUT = 5  # seconds


# from https://findwork.dev/blog/advanced-usage-python-requests-timeouts-retries-hooks/
class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs) -> None:
        self.timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs) -> Response:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class NoRetryAdapter(HTTPAdapter):
    def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ):
        return super().send(request, stream, timeout, verify, cert, proxies)


class UnauthorizedException(Exception):
    def __init__(self, api_key):
        api_key_prefix = api_key[:10] if api_key else ""
        super().__init__(
            f"Prefab attempts to fetch data are unauthorized using api key starting with {api_key_prefix}. Please check your api key."
        )


class HostIterator:
    def __init__(self, hosts):
        self.hosts = hosts
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if not self.hosts:
            raise StopIteration
        host = self.hosts[self.index]
        self.index = (self.index + 1) % len(self.hosts)
        return host


# --- Simple LRU Cache Implementation ---


@dataclass
class CacheEntry:
    data: bytes
    etag: str
    expires_at: float
    url: str  # The full URL from the successful response


class LRUCache:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self.cache = OrderedDict()

    def get(self, key):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value  # Mark as recently used.
            return value
        except KeyError:
            return None

    def set(self, key, value):
        if key in self.cache:
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = value

    def clear(self):
        self.cache.clear()

    def __len__(self):
        return len(self.cache)


class ApiClient:
    def __init__(self, options):
        """
        :param options: An object with attributes such as:
            - prefab_api_urls: list of API host URLs (e.g. ["https://a.example.com", "https://b.example.com"])
            - version: version string
        """
        self.hosts = options.reforge_api_urls
        self.session = requests.Session()
        self.session.mount("https://", requests.adapters.HTTPAdapter())
        self.session.mount("http://", requests.adapters.HTTPAdapter())
        self.session.headers.update(
            {
                "X-Reforge-Client-Version": f"reforge-python-{getattr(options, 'version', 'development')}"
            }
        )
        # Initialize a cache (here with a maximum of 2 entries).
        self.cache = LRUCache(max_size=2)

    def get_host(self, attempt_number, host_list):
        return host_list[attempt_number % len(host_list)]

    def _get_attempt_number(self) -> int:
        """
        Retrieve the current attempt number from tenacity's statistics if available,
        otherwise default to 1.
        """
        stats = getattr(self.resilient_request, "statistics", None)
        if stats is None:
            return 1
        return stats.get("attempt_number", 1)

    def _build_url(self, path, hosts: list[str] = None) -> str:
        """
        Build the full URL using host-selection logic.
        """
        attempt_number = self._get_attempt_number()
        host = self.get_host(attempt_number - 1, hosts or self.hosts)
        return f"{host.rstrip('/')}/{path.lstrip('/')}"

    def _get_cached_response(self, url: str) -> Response:
        """
        If a valid cache entry exists for the given URL, return a synthetic Response.
        """
        now = time.time()
        entry = self.cache.get(url)
        if entry is not None and entry.expires_at > now:
            resp = Response()
            resp._content = entry.data
            resp.status_code = 200
            resp.headers = {"ETag": entry.etag, "X-Cache": "HIT"}
            resp.url = entry.url
            return resp
        return None

    def _apply_cache_headers(self, url: str, kwargs: dict) -> dict:
        """
        If a stale cache entry exists, add its ETag as an 'If-None-Match' header.
        """
        entry = self.cache.get(url)
        headers = kwargs.get("headers", {}).copy()
        if entry is not None and entry.etag:
            headers["If-None-Match"] = entry.etag
        kwargs["headers"] = headers
        return kwargs

    def _update_cache(self, url: str, response: Response) -> None:
        """
        If the response is cacheable (status 200, and Cache-Control does not include 'no-store'),
        update the cache. If Cache-Control includes 'no-cache', mark the cache entry as immediately expired,
        so that subsequent requests always trigger revalidation.
        """
        cache_control = response.headers.get("Cache-Control", "")
        if "no-store" in cache_control.lower():
            return

        etag = response.headers.get("ETag")
        max_age = 0
        m = re.search(r"max-age=(\d+)", cache_control)
        if m:
            max_age = int(m.group(1))

        # If 'no-cache' is present, then even though we may store the response,
        # we treat it as expired immediately so that every subsequent request is revalidated.
        if "no-cache" in cache_control.lower():
            expires_at = time.time()  # Immediately expired.
        else:
            expires_at = time.time() + max_age if max_age > 0 else 0

        if (etag is not None or max_age > 0) and expires_at > time.time():
            self.cache.set(
                url,
                CacheEntry(
                    data=response.content,
                    etag=etag,
                    expires_at=expires_at,
                    url=response.url,
                ),
            )
            response.headers["X-Cache"] = "MISS"

    def _send_request(self, method: str, url: str, **kwargs) -> Response:
        """
        Hook method to perform the actual HTTP request.
        """
        return self.session.request(method, url, **kwargs)

    @retry(
        stop=stop_after_delay(8),
        wait=wait_exponential(multiplier=1, min=0.05, max=2),
        retry=retry_if_exception_type((RequestException, ConnectionError, OSError)),
    )
    def resilient_request(
        self,
        path,
        method="GET",
        allow_cache: bool = False,
        hosts: list[str] = None,
        **kwargs,
    ) -> Response:
        """
        Makes a resilient (retrying) request.

        If allow_cache is True and the request method is GET, caching logic is applied.
        This includes:
          - Checking the cache and returning a synthetic response if valid.
          - Adding an 'If-None-Match' header when a stale entry exists.
          - Handling a 304 (Not Modified) response by returning the cached entry.
          - Caching a 200 response if Cache-Control permits.
        """
        url = self._build_url(path, hosts)
        if method.upper() == "GET" and allow_cache:
            cached = self._get_cached_response(url)
            if cached:
                return cached
            kwargs = self._apply_cache_headers(url, kwargs)
        response = self._send_request(method, url, **kwargs)
        if method.upper() == "GET" and allow_cache:
            if response.status_code == 304:
                cached = self.cache.get(url)
                if cached:
                    resp = Response()
                    resp._content = cached.data
                    resp.status_code = 200
                    resp.headers = {"ETag": cached.etag, "X-Cache": "HIT"}
                    resp.url = cached.url
                    return resp
            self._update_cache(url, response)
        return response
