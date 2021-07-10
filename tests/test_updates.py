#!/usr/bin/env python3

"""Tests for the updates functionality."""

import unittest
from unittest.mock import patch, Mock, call
from ip150 import Paradox_IP150, Paradox_IP150_Error


class TestUpdates(unittest.TestCase):
    """Tests for the updates functionality."""

    def test_updates_no_on_update(self):
        """Test if get_updates with on_udpate=None raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.get_updates()
        self.assertEqual(str(cm.exception),
                         'The callable on_update must be provided.')
        self.assertIsNone(ip_module._updates)

    def test_updates_invalid_interval(self):
        """Test if passing invalid poll_interval raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.get_updates(on_update=Mock(), poll_interval=0)
        self.assertEqual(
                str(cm.exception),
                'The polling interval must be greater than 0.0 seconds.')
        self.assertIsNone(ip_module._updates)

        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.get_updates(on_update=Mock(), poll_interval=-1)
        self.assertEqual(
                str(cm.exception),
                'The polling interval must be greater than 0.0 seconds.')
        self.assertIsNone(ip_module._updates)

    @patch('ip150.threading.Thread')
    def test_updates_start(self, mock_thread):
        """Test starting the _updates thread."""
        on_update = Mock()
        on_error = Mock()
        userdata = Mock()
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        ip_module.get_updates(on_update=on_update, on_error=on_error,
                              userdata=userdata, poll_interval=2.0)
        mock_thread.assert_called_with(target=ip_module._get_updates,
                                       args=(on_update, on_error, userdata,
                                             2.0),
                                       daemon=True)
        ip_module._updates.start.assert_called_once()
        self.assertIsNotNone(ip_module._updates)

    def test_updates_cancel_not_running(self):
        """Test if cancelling _updates before starting it raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.cancel_updates()
        self.assertEqual(
                str(cm.exception),
                'Not currently getting updates. Use get_updates() first.')

    @patch('ip150.threading.Event')  # __init__ creates _stop_updates
    def test_updates_cancel(self, mock_event):
        """Test cancelling the _updates thread."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        _updates = Mock()
        ip_module._updates = _updates
        ip_module.cancel_updates()
        ip_module._stop_updates.set.assert_called_once()
        self.assertIsNone(ip_module._updates)

    @patch('ip150.threading.Event')  # __init__ creates _stop_updates
    @patch('ip150.Paradox_IP150.get_info')
    def test_updates_body_first_full(self, mock_info, mock_event):
        """Test the operation of the _updates thread.

        We test whether the full status is reported through on_update when the
        _updates thread is first started.

        Then we test if no change in state produces no on_update call.

        Then we simulate the state changing and test if the state difference
        algorithm is working properly.

        on_error() should not be called during this test.
        """
        ip_module = Paradox_IP150('http://127.0.0.1')
        # _get_updates will loop until _stop_updates.wait() returns True
        ip_module._stop_updates.wait.side_effect = [False, False,
                                                    False, False,
                                                    True]
        initial_state = {
                'zones_status': [(1, 'Closed'), (2, 'Closed'), (3, 'Open')],
                'areas_status': [(1, 'Armed'), (2, 'Ready')],
            }
        updated_state = {
                'zones_status': [(1, 'Closed'), (2, 'Closed'), (3, 'Closed')],
                'areas_status': [(1, 'Pending'), (2, 'Ready')],
            }
        state_update = {
                'zones_status': [(3, 'Closed')],
                'areas_status': [(1, 'Pending')]
            }
        mock_info.side_effect = [initial_state, initial_state,
                                 updated_state, updated_state]
        on_update = Mock()
        on_error = Mock()
        userdata = Mock()
        ip_module._get_updates(on_update, on_error, userdata, 1.0)
        self.assertEqual(mock_info.call_count, 4)
        on_error.assert_not_called()
        # on_update should be called once for the first full report and once
        # with the state update
        self.assertEqual(on_update.call_count, 2)
        on_update.assert_has_calls([call(initial_state, userdata),
                                    call(state_update, userdata)])
        # The last True returned by _stop_updates.wait() should cause the
        # thread to stop and clear the stop signal.
        ip_module._stop_updates.clear.assert_called_once()


if __name__ == '__main__':
    # This is not useful because the ip150 module will not be found if
    # executed directly.
    # Run `python3 -m unittest` in the root of the repository to run all tests.
    unittest.main()
