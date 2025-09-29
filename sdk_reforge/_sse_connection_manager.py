import base64
import time
from typing import Optional, Callable

import sseclient  # type: ignore
from requests import Response

from sdk_reforge._internal_logging import InternalLogger
from sdk_reforge._requests import ApiClient, UnauthorizedException
import prefab_pb2 as Prefab
from sdk_reforge.config_sdk_interface import ConfigSDKInterface

SHORT_CONNECTION_THRESHOLD = 2  # seconds
CONSECUTIVE_SHORT_CONNECTION_LIMIT = 2  # times
MIN_BACKOFF_TIME = 1  # seconds
MAX_BACKOFF_TIME = 30  # seconds


class TooQuickConnectionException(Exception):
    pass


logger = InternalLogger(__name__)


class SSEConnectionManager:
    def __init__(
        self,
        api_client: ApiClient,
        config_client: ConfigSDKInterface,
        urls: list[str],
    ):
        self.api_client = api_client
        self.config_client = config_client
        self.sse_client: Optional[sseclient.SSEClient] = None
        self.timing = Timing()
        self.urls = urls

    def streaming_loop(self) -> None:
        too_short_connection_count = 0
        backoff_time = MIN_BACKOFF_TIME

        while self.config_client.continue_connection_processing():
            try:
                logger.debug("Starting streaming connection")
                headers = {
                    "Last-Event-ID": f"{self.config_client.highwater_mark()}",
                    "accept": "text/event-stream",
                }
                response = self.api_client.resilient_request(
                    "/api/v2/sse/config",
                    headers=headers,
                    stream=True,
                    auth=("authuser", self.config_client.options.api_key),
                    timeout=(5, 60),
                    hosts=self.urls,
                )
                response.raise_for_status()
                if response.ok:
                    elapsed_time = self.timing.time_execution(
                        lambda: self.process_response(response)
                    )
                    if elapsed_time < SHORT_CONNECTION_THRESHOLD:
                        too_short_connection_count += 1
                        if (
                            too_short_connection_count
                            >= CONSECUTIVE_SHORT_CONNECTION_LIMIT
                        ):
                            raise TooQuickConnectionException()
                    else:
                        too_short_connection_count = 0
                        backoff_time = MIN_BACKOFF_TIME
                    time.sleep(backoff_time)
            except UnauthorizedException:
                self.config_client.handle_unauthorized_response()
            except TooQuickConnectionException as e:
                logger.debug(f"Connection ended quickly: {str(e)}. Will apply backoff.")
                backoff_time = min(backoff_time * 2, MAX_BACKOFF_TIME)
                time.sleep(backoff_time)
            except Exception as e:
                if not self.config_client.is_shutting_down():
                    logger.warning(
                        f"Streaming connection error: {str(e)}, Will retry in {backoff_time} seconds"
                    )
                    backoff_time = min(backoff_time * 2, MAX_BACKOFF_TIME)
                    time.sleep(backoff_time)

    """
    Hand off a successful response here for processing
    """

    def process_response(self, response: Response) -> None:
        self.sse_client = sseclient.SSEClient(response)
        if self.sse_client is not None:
            for event in self.sse_client.events():
                if self.config_client.is_shutting_down():
                    logger.info("Client is shutting down, exiting SSE event loop")
                    return
                if event.data:
                    decoded_data = base64.b64decode(event.data)
                    if not decoded_data or len(decoded_data) == 0:
                        logger.warning(
                            "Received zero-byte config payload from SSE stream, treating as connection error"
                        )
                        # Return early to trigger reconnection logic
                        return
                    configs = Prefab.Configs.FromString(decoded_data)
                    self.config_client.load_configs(configs, "sse_streaming")
            self.sse_client.close()
            self.sse_client = None


class Timing:
    def time_execution(self, func: Callable[[], None]) -> float:
        """Executes the given function and returns the time it took to execute."""
        start_time = self.now()
        func()  # Execute the block of code
        return self.now() - start_time

    def now(self) -> float:
        """Get the current time. This can be mocked in tests."""
        return time.time()
