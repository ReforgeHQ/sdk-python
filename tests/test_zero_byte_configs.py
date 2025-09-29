from __future__ import annotations

import unittest
from unittest.mock import Mock, patch, MagicMock
import base64

from sdk_reforge.config_sdk import ConfigSDK
from sdk_reforge._sse_connection_manager import SSEConnectionManager
import prefab_pb2 as Prefab


class TestZeroByteConfigHandling(unittest.TestCase):
    @patch("sdk_reforge.config_sdk.logger")
    def test_http_config_zero_byte_payload(self, mock_logger: MagicMock) -> None:
        """Test that zero-byte HTTP config responses are treated as errors"""
        # Create mock objects
        mock_api_client = Mock()
        mock_response = Mock()
        mock_response.ok = True
        mock_response.content = b""  # Zero-byte response
        mock_api_client.resilient_request.return_value = mock_response

        # Create ConfigSDK with mocked dependencies
        options = Mock()
        options.api_key = "test_key"
        config_sdk = ConfigSDK(options)
        config_sdk.api_client = mock_api_client
        config_sdk.config_loader = Mock()
        config_sdk.config_loader.highwater_mark = 123

        # Test that load_checkpoint_from_api_cdn returns False for zero-byte response
        result = config_sdk.load_checkpoint_from_api_cdn()

        self.assertFalse(result)
        mock_logger.warning.assert_called_with(
            "Received zero-byte config payload from remote_cdn_api, treating as connection error"
        )

    @patch("sdk_reforge.config_sdk.logger")
    def test_http_config_valid_payload(self, mock_logger: MagicMock) -> None:
        """Test that valid HTTP config responses are processed normally"""
        # Create mock objects
        mock_api_client = Mock()
        mock_response = Mock()
        mock_response.ok = True

        # Create a valid Prefab.Configs message
        configs = Prefab.Configs()
        config = configs.configs.add()
        config.key = "test_key"
        valid_content = configs.SerializeToString()
        mock_response.content = valid_content

        mock_api_client.resilient_request.return_value = mock_response

        # Create ConfigSDK with mocked dependencies
        options = Mock()
        options.api_key = "test_key"
        config_sdk = ConfigSDK(options)
        config_sdk.api_client = mock_api_client
        config_sdk.config_loader = Mock()
        config_sdk.config_loader.highwater_mark = 123
        config_sdk.load_configs = Mock()

        # Test that load_checkpoint_from_api_cdn returns True for valid response
        result = config_sdk.load_checkpoint_from_api_cdn()

        self.assertTrue(result)
        config_sdk.load_configs.assert_called_once()
        # Check that the specific zero-byte warning was not called
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        self.assertNotIn(
            "call('Received zero-byte config payload from remote_cdn_api, treating as connection error')",
            warning_calls,
        )

    def test_sse_config_zero_byte_payload(self) -> None:
        """Test that zero-byte SSE config payloads trigger reconnection"""
        # Create mock objects
        mock_api_client = Mock()
        mock_config_client = Mock()
        mock_config_client.is_shutting_down.return_value = False

        # Create SSEConnectionManager
        sse_manager = SSEConnectionManager(
            mock_api_client, mock_config_client, ["https://test.example.com"]
        )

        # Mock SSE event with a base64 string that will decode to empty bytes
        # We need a non-empty string that produces empty bytes when decoded
        # In practice, this would happen when the server sends an empty base64 string
        # For testing, we'll use a mock that bypasses base64 entirely
        mock_event = Mock()
        mock_event.data = "dummy"  # Non-empty string to pass the if check

        mock_sse_client = Mock()
        mock_sse_client.events.return_value = iter([mock_event])
        mock_sse_client.close = Mock()

        mock_response = Mock()

        with patch(
            "sdk_reforge._sse_connection_manager.sseclient.SSEClient",
            return_value=mock_sse_client,
        ):
            with patch(
                "sdk_reforge._sse_connection_manager.base64.b64decode"
            ) as mock_b64decode:
                mock_b64decode.return_value = b""  # Return empty bytes
                with patch("sdk_reforge._sse_connection_manager.logger") as mock_logger:
                    # The process_response method should return early on zero-byte payload
                    sse_manager.process_response(mock_response)

                    # Verify that warning was logged and configs were not loaded
                    mock_logger.warning.assert_called_with(
                        "Received zero-byte config payload from SSE stream, treating as connection error"
                    )

        mock_config_client.load_configs.assert_not_called()
        # SSE client should not be closed since we returned early
        mock_sse_client.close.assert_not_called()

    @patch("sdk_reforge._sse_connection_manager.logger")
    def test_sse_config_valid_payload(self, mock_logger: MagicMock) -> None:
        """Test that valid SSE config payloads are processed normally"""
        # Create mock objects
        mock_api_client = Mock()
        mock_config_client = Mock()
        mock_config_client.is_shutting_down.return_value = False

        # Create SSEConnectionManager
        sse_manager = SSEConnectionManager(
            mock_api_client, mock_config_client, ["https://test.example.com"]
        )

        # Create a valid Prefab.Configs message
        configs = Prefab.Configs()
        config = configs.configs.add()
        config.key = "test_key"
        valid_content = configs.SerializeToString()

        # Mock SSE event with valid payload
        mock_event = Mock()
        mock_event.data = base64.b64encode(valid_content).decode("utf-8")

        mock_sse_client = Mock()
        mock_sse_client.events.return_value = iter([mock_event])
        mock_sse_client.close = Mock()

        mock_response = Mock()

        with patch(
            "sdk_reforge._sse_connection_manager.sseclient.SSEClient",
            return_value=mock_sse_client,
        ):
            with patch(
                "sdk_reforge._sse_connection_manager.Prefab.Configs.FromString"
            ) as mock_from_string:
                mock_from_string.return_value = configs
                sse_manager.process_response(mock_response)

        # Verify that configs were loaded and no warning was logged
        mock_config_client.load_configs.assert_called_once_with(
            configs, "sse_streaming"
        )
        mock_logger.warning.assert_not_called()
        # SSE client should be closed after successful processing
        mock_sse_client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
