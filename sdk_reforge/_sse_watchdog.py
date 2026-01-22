import threading
import time
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from ._internal_logging import InternalLogger

if TYPE_CHECKING:
    from .config_sdk_interface import ConfigSDKInterface

logger = InternalLogger(__name__)

DEFAULT_CHECK_INTERVAL: float = 60  # seconds
DEFAULT_MAX_SILENCE: float = 120  # seconds (4 missed 30s keepalives)


class WatchdogResponseWrapper:
    """Wraps a response to touch the watchdog on any data received.

    This allows the watchdog to track when ANY data is received from the SSE
    connection, including keepalive comments that sseclient filters out.
    """

    def __init__(self, response: Any, on_data_received: Callable[[], None]) -> None:
        self._response = response
        self._on_data_received = on_data_received

    def __iter__(self) -> Iterator[Any]:
        for chunk in self._response:
            self._on_data_received()
            yield chunk

    def close(self) -> None:
        self._response.close()


class SSEWatchdog:
    """Monitors SSE connection health and triggers recovery when stuck.

    The watchdog runs in a separate thread and periodically checks if SSE data
    has been received recently. If no data (including keepalives) has been
    received for max_silence seconds, it:
    1. Logs a warning
    2. Polls the checkpoint API to get fresh config data
    3. Closes the SSE connection to force reconnection
    """

    def __init__(
        self,
        config_client: "ConfigSDKInterface",
        poll_fallback_fn: Callable[[], None],
        get_sse_client_fn: Callable[[], Any],
        check_interval: float = DEFAULT_CHECK_INTERVAL,
        max_silence: float = DEFAULT_MAX_SILENCE,
    ) -> None:
        """Initialize the watchdog.

        Args:
            config_client: The config client interface for checking shutdown state
            poll_fallback_fn: Function to call to poll for fresh config data
            get_sse_client_fn: Function that returns the current SSE client (or None)
            check_interval: How often to check for silence (seconds)
            max_silence: Trigger recovery after this many seconds of no data
        """
        self.config_client = config_client
        self.poll_fallback_fn = poll_fallback_fn
        self.get_sse_client_fn = get_sse_client_fn
        self.check_interval = check_interval
        self.max_silence = max_silence
        self.last_activity = time.time()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def touch(self) -> None:
        """Called when any SSE data is received (including keepalives)."""
        self.last_activity = time.time()

    def start(self) -> None:
        """Start the watchdog thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watchdog thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        """Main watchdog loop."""
        while not self._stop.wait(self.check_interval):
            if self.config_client.is_shutting_down():
                break

            silence = time.time() - self.last_activity
            if silence > self.max_silence:
                self._trigger_recovery(silence)

    def _trigger_recovery(self, silence: float) -> None:
        """Trigger recovery actions when SSE appears stuck."""
        logger.warning(
            f"SSE connection appears stuck (no activity for {silence:.0f}s), "
            "triggering recovery"
        )

        # 1. Poll for fresh data immediately
        try:
            self.poll_fallback_fn()
            logger.info("Fallback poll completed successfully")
        except Exception as e:
            logger.warning(f"Fallback poll failed: {e}")

        # 2. Force SSE reconnection by closing current connection
        try:
            sse_client = self.get_sse_client_fn()
            if sse_client:
                sse_client.close()
                logger.debug("Closed SSE client to force reconnection")
        except Exception:
            pass  # Best effort

        # Reset activity timer after recovery attempt
        self.last_activity = time.time()
