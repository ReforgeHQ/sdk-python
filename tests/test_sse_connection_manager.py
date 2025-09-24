import unittest
from unittest.mock import Mock, patch, call

from requests import HTTPError

# Import from the correct module
from sdk_reforge._sse_connection_manager import (
    SSEConnectionManager,
    MIN_BACKOFF_TIME,
)
from sdk_reforge._requests import UnauthorizedException


class TestSSEConnectionManager(unittest.TestCase):
    def setUp(self):
        self.api_client = Mock()
        self.config_client = Mock()
        self.config_client.continue_connection_processing.side_effect = [
            True,
            True,
            False,
        ]
        self.config_client.highwater_mark.return_value = "123"
        self.config_client.options.api_key = "test_api_key"
        self.sse_manager = SSEConnectionManager(
            self.api_client, self.config_client, ["https://stream.test-prefab.cloud"]
        )

    @patch("sdk_reforge._sse_connection_manager.time.sleep")
    def test_backoff_on_failed_response(self, mock_sleep):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
        self.api_client.resilient_request.return_value = mock_response

        # Ensure the loop runs three times before exiting
        self.config_client.continue_connection_processing.side_effect = [
            True,
            True,
            True,
            False,
        ]
        self.config_client.is_shutting_down.return_value = False

        self.sse_manager.streaming_loop()

        expected_calls = [
            call(MIN_BACKOFF_TIME * 2),
            call(MIN_BACKOFF_TIME * 4),
            call(MIN_BACKOFF_TIME * 8),
        ]

        mock_sleep.assert_has_calls(expected_calls, any_order=False)

        self.api_client.resilient_request.assert_called_with(
            "/api/v1/sse/config",
            headers={"x-prefab-start-at-id": "123", "accept": "text/event-stream"},
            stream=True,
            auth=("authuser", "test_api_key"),
            timeout=(5, 60),
            hosts=["https://stream.test-prefab.cloud"],
        )

        # Check that resilient_request was called three times
        self.assertEqual(self.api_client.resilient_request.call_count, 3)

    @patch("sdk_reforge._sse_connection_manager.Timing")
    @patch("sdk_reforge._sse_connection_manager.time.sleep")
    def test_backoff_on_too_quick_connection(self, mock_sleep, mock_timing):
        self.sse_manager = SSEConnectionManager(
            self.api_client, self.config_client, ["https://stream.test-prefab.cloud"]
        )

        # Mock Timing instance returned from the constructor
        mock_timing_instance = mock_timing.return_value
        mock_timing_instance.time_execution.side_effect = [
            1,
            0,
            0,
            0,
        ]  # Simulate elapsed time

        # Mock other components
        self.config_client.continue_connection_processing.side_effect = [
            True,
            True,
            True,
            True,
            False,
        ]
        mock_response = Mock()
        mock_response.ok = True
        self.api_client.resilient_request.return_value = mock_response
        self.sse_manager.process_response = Mock()

        # Run the test case
        self.sse_manager.streaming_loop()

        # Assert that sleep was called with backoff time
        self.assertEqual(mock_sleep.call_count, 4)

        expected_calls = [
            call(MIN_BACKOFF_TIME),
            call(MIN_BACKOFF_TIME * 2),
            call(MIN_BACKOFF_TIME * 4),
            call(MIN_BACKOFF_TIME * 8),
        ]

        mock_sleep.assert_has_calls(expected_calls, any_order=False)

        self.api_client.resilient_request.assert_called_with(
            "/api/v1/sse/config",
            headers={"x-prefab-start-at-id": "123", "accept": "text/event-stream"},
            stream=True,
            auth=("authuser", "test_api_key"),
            timeout=(5, 60),
            hosts=["https://stream.test-prefab.cloud"],
        )

    @patch("sdk_reforge._sse_connection_manager.time.sleep")
    def test_backoff_on_unauthorized_exception(self, mock_sleep):
        self.config_client.continue_connection_processing.side_effect = [True, False]
        self.api_client.resilient_request.side_effect = UnauthorizedException("the key")

        self.sse_manager.streaming_loop()

        self.config_client.handle_unauthorized_response.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("sdk_reforge._sse_connection_manager.time.sleep")
    def test_backoff_on_general_exception(self, mock_sleep):
        self.api_client.resilient_request.side_effect = Exception("Test exception")
        self.config_client.continue_connection_processing.side_effect = [
            True,
            True,
            True,
            False,
        ]
        self.config_client.is_shutting_down.return_value = False

        self.sse_manager.streaming_loop()
        self.assertEqual(mock_sleep.call_count, 3)
        expected_calls = [
            call(MIN_BACKOFF_TIME * 2),
            call(MIN_BACKOFF_TIME * 4),
            call(MIN_BACKOFF_TIME * 8),
        ]

        mock_sleep.assert_has_calls(expected_calls, any_order=False)
        self.api_client.resilient_request.assert_called_with(
            "/api/v1/sse/config",
            headers={"x-prefab-start-at-id": "123", "accept": "text/event-stream"},
            stream=True,
            auth=("authuser", "test_api_key"),
            timeout=(5, 60),
            hosts=["https://stream.test-prefab.cloud"],
        )

    @patch("sdk_reforge._sse_connection_manager.Timing")
    @patch("sdk_reforge._sse_connection_manager.time.sleep")
    def test_backoff_reset_on_successful_connection(self, mock_sleep, mock_timing):
        self.sse_manager = SSEConnectionManager(
            self.api_client, self.config_client, ["https://stream.test-prefab.cloud"]
        )

        # Mock Timing instance returned from the constructor
        mock_timing_instance = mock_timing.return_value
        mock_timing_instance.time_execution.side_effect = [
            1,
            1,
            1,
            10,
            10,
        ]  # Simulate elapsed time

        # Mock other components
        self.config_client.continue_connection_processing.side_effect = [
            True,
            True,
            True,
            True,
            False,
        ]
        mock_response = Mock()
        mock_response.ok = True
        self.api_client.resilient_request.return_value = mock_response
        self.sse_manager.process_response = Mock()

        # Run the test case
        self.sse_manager.streaming_loop()

        # Assert that sleep was called with backoff time
        self.assertEqual(mock_sleep.call_count, 4)

        expected_calls = [
            call(MIN_BACKOFF_TIME),
            call(MIN_BACKOFF_TIME * 2),
            call(MIN_BACKOFF_TIME * 4),
            call(MIN_BACKOFF_TIME),
        ]

        mock_sleep.assert_has_calls(expected_calls, any_order=False)
        self.api_client.resilient_request.assert_called_with(
            "/api/v1/sse/config",
            headers={"x-prefab-start-at-id": "123", "accept": "text/event-stream"},
            stream=True,
            auth=("authuser", "test_api_key"),
            timeout=(5, 60),
            hosts=["https://stream.test-prefab.cloud"],
        )

    def test_process_response(self):
        mock_response = Mock()
        mock_sse_client = Mock()
        mock_event = Mock(data="test_data")
        mock_sse_client.events.return_value = [mock_event]

        with patch(
            "sdk_reforge._sse_connection_manager.sseclient.SSEClient",
            return_value=mock_sse_client,
        ) as mock_sse_client_class:
            with patch(
                "sdk_reforge._sse_connection_manager.base64.b64decode",
                return_value=b"test_decoded",
            ) as mock_b64decode:
                with patch(
                    "sdk_reforge._sse_connection_manager.Prefab.Configs.FromString"
                ) as mock_from_string:
                    self.config_client.is_shutting_down.return_value = False
                    self.sse_manager.process_response(mock_response)

        mock_sse_client_class.assert_called_once_with(mock_response)
        mock_b64decode.assert_called_once_with("test_data")
        mock_from_string.assert_called_once_with(b"test_decoded")
        self.config_client.load_configs.assert_called_once()
        mock_sse_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
