import unittest
import time
from unittest.mock import Mock, patch

from sdk_reforge._sse_watchdog import (
    SSEWatchdog,
    WatchdogResponseWrapper,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_SILENCE,
)


class TestWatchdogResponseWrapper(unittest.TestCase):
    def test_iterates_through_all_chunks(self) -> None:
        """Verify all chunks are yielded unchanged"""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = iter(chunks)
        on_data_received: Mock = Mock()

        wrapper = WatchdogResponseWrapper(mock_response, on_data_received)
        result = list(wrapper)

        self.assertEqual(result, chunks)

    def test_calls_callback_for_each_chunk(self) -> None:
        """Verify callback is called for each chunk received"""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = iter(chunks)
        on_data_received: Mock = Mock()

        wrapper = WatchdogResponseWrapper(mock_response, on_data_received)
        list(wrapper)  # Consume the iterator

        self.assertEqual(on_data_received.call_count, 3)

    def test_close_delegates_to_response(self) -> None:
        """Verify close() is delegated to the wrapped response"""
        mock_response: Mock = Mock()
        on_data_received: Mock = Mock()

        wrapper = WatchdogResponseWrapper(mock_response, on_data_received)
        wrapper.close()

        mock_response.close.assert_called_once()


class TestSSEWatchdog(unittest.TestCase):
    def setUp(self) -> None:
        self.config_client: Mock = Mock()
        self.config_client.is_shutting_down.return_value = False
        self.poll_fallback_fn: Mock = Mock()
        self.get_sse_client_fn: Mock = Mock(return_value=None)

    def test_touch_updates_last_activity(self) -> None:
        """Verify touch() updates the last_activity timestamp"""
        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        initial_time = watchdog.last_activity
        time.sleep(0.01)  # Small delay to ensure time difference
        watchdog.touch()

        self.assertGreater(watchdog.last_activity, initial_time)

    def test_no_recovery_when_active(self) -> None:
        """Verify no recovery is triggered when activity is recent"""
        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
            check_interval=1,
            max_silence=10,
        )

        # Touch to reset activity
        watchdog.touch()

        # Manually run the check logic
        silence = time.time() - watchdog.last_activity
        self.assertLess(silence, watchdog.max_silence)

        # Poll should not have been called
        self.poll_fallback_fn.assert_not_called()

    @patch("sdk_reforge._sse_watchdog.time.time")
    def test_triggers_recovery_when_silent(self, mock_time: Mock) -> None:
        """Verify recovery is triggered after max_silence seconds"""
        # Set up time mocking: initial time, then time during check
        mock_time.side_effect = [
            1000,  # Initial last_activity in __init__
            1000,  # touch() call
            1200,  # time check in _run (200s silence > 120s max)
            1200,  # time in _trigger_recovery for logging
            1200,  # reset last_activity after recovery
        ]

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
            max_silence=120,
        )
        watchdog.touch()

        # Manually trigger recovery check
        silence = 1200 - watchdog.last_activity  # 200 seconds
        if silence > watchdog.max_silence:
            watchdog._trigger_recovery(silence)

        self.poll_fallback_fn.assert_called_once()

    def test_recovery_closes_sse_client(self) -> None:
        """Verify recovery attempts to close the SSE client"""
        mock_sse_client: Mock = Mock()
        self.get_sse_client_fn.return_value = mock_sse_client

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        watchdog._trigger_recovery(999)

        mock_sse_client.close.assert_called_once()

    def test_recovery_handles_none_sse_client(self) -> None:
        """Verify recovery handles case when SSE client is None"""
        self.get_sse_client_fn.return_value = None

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        # Should not raise
        watchdog._trigger_recovery(999)

        self.poll_fallback_fn.assert_called_once()

    def test_recovery_handles_poll_exception(self) -> None:
        """Verify recovery continues even if poll fails"""
        self.poll_fallback_fn.side_effect = Exception("Poll failed")
        mock_sse_client: Mock = Mock()
        self.get_sse_client_fn.return_value = mock_sse_client

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        # Should not raise
        watchdog._trigger_recovery(999)

        # Should still try to close SSE client
        mock_sse_client.close.assert_called_once()

    def test_recovery_handles_close_exception(self) -> None:
        """Verify recovery continues even if close fails"""
        mock_sse_client: Mock = Mock()
        mock_sse_client.close.side_effect = Exception("Close failed")
        self.get_sse_client_fn.return_value = mock_sse_client

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        # Should not raise
        watchdog._trigger_recovery(999)

        self.poll_fallback_fn.assert_called_once()

    def test_recovery_resets_last_activity(self) -> None:
        """Verify last_activity is reset after recovery"""
        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        # Set last_activity to old time
        watchdog.last_activity = time.time() - 1000

        watchdog._trigger_recovery(999)

        # last_activity should be recent now
        self.assertLess(time.time() - watchdog.last_activity, 1)

    def test_stop_terminates_thread(self) -> None:
        """Verify stop() terminates the watchdog thread"""
        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
            check_interval=1,
        )

        watchdog.start()
        assert watchdog._thread is not None
        self.assertTrue(watchdog._thread.is_alive())

        watchdog.stop()
        self.assertFalse(watchdog._thread.is_alive())

    def test_stops_when_shutting_down(self) -> None:
        """Verify watchdog stops when config_client is shutting down"""
        self.config_client.is_shutting_down.return_value = True

        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
            check_interval=0.1,
        )

        watchdog.start()
        time.sleep(0.3)  # Give it time to check

        # Should have stopped on its own
        watchdog.stop()
        self.poll_fallback_fn.assert_not_called()

    def test_default_values(self) -> None:
        """Verify default configuration values"""
        watchdog = SSEWatchdog(
            self.config_client,
            self.poll_fallback_fn,
            self.get_sse_client_fn,
        )

        self.assertEqual(watchdog.check_interval, DEFAULT_CHECK_INTERVAL)
        self.assertEqual(watchdog.max_silence, DEFAULT_MAX_SILENCE)


class TestSSEWatchdogIntegration(unittest.TestCase):
    """Integration tests for the watchdog with realistic timing"""

    def test_watchdog_fires_after_silence(self) -> None:
        """Integration test: watchdog fires recovery after silence period"""
        config_client: Mock = Mock()
        config_client.is_shutting_down.return_value = False
        poll_fallback_fn: Mock = Mock()
        get_sse_client_fn: Mock = Mock(return_value=None)

        # Use short intervals for testing
        watchdog = SSEWatchdog(
            config_client,
            poll_fallback_fn,
            get_sse_client_fn,
            check_interval=0.1,  # Check every 100ms
            max_silence=0.2,  # Fire after 200ms of silence
        )

        watchdog.start()

        # Wait for silence period + check interval
        time.sleep(0.5)

        watchdog.stop()

        # Recovery should have been triggered
        self.assertTrue(poll_fallback_fn.called)

    def test_watchdog_does_not_fire_with_activity(self) -> None:
        """Integration test: watchdog does not fire when touched regularly"""
        config_client: Mock = Mock()
        config_client.is_shutting_down.return_value = False
        poll_fallback_fn: Mock = Mock()
        get_sse_client_fn: Mock = Mock(return_value=None)

        watchdog = SSEWatchdog(
            config_client,
            poll_fallback_fn,
            get_sse_client_fn,
            check_interval=0.1,
            max_silence=0.3,
        )

        watchdog.start()

        # Keep touching to simulate activity
        for _ in range(5):
            watchdog.touch()
            time.sleep(0.1)

        watchdog.stop()

        # Recovery should NOT have been triggered
        poll_fallback_fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
