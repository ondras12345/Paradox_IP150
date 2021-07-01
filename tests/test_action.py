#!/usr/bin/env python3

"""Tests for actions (arming, ...)."""

import unittest
from unittest.mock import patch, Mock
from ip150 import Paradox_IP150, Paradox_IP150_Error


class TestActions(unittest.TestCase):
    """Tests for actions (arming, ...)."""

    def test_area_action_invalid_area(self):
        """Test if providing invalid area number raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module.logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.set_area_action(0, 'Arm')
        self.assertEqual(str(cm.exception), 'Invalid area provided.')

    def test_area_action_invalid_action(self):
        """Test if providing invalid action raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module.logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.set_area_action(1, 'test')
        self.assertEqual(
            str(cm.exception),
            'Invalid action "test" provided. Valid '
            'actions are [\'Disarm\', \'Arm\', \'Arm_sleep\', \'Arm_stay\']'
            )

    @patch('ip150.requests')
    def test_area_action_fail(self, mock_requests):
        """Test if error is raised when IP150 does not return 200 OK."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module.logged_in = True
        page = Mock()
        page.status_code = 404  # Page Not Found
        mock_requests.get.return_value = page
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.set_area_action(2, 'Arm')
        self.assertEqual(str(cm.exception), 'Error setting the area action')
        mock_requests.get.assert_called_once()
        mock_requests.get.assert_called_with(
                'http://127.0.0.1/statuslive.html',
                params={'area': '01', 'value': 'r'},
                verify=False
                )

    @patch('ip150.requests')
    def test_area_action_successful(self, mock_requests):
        """Test a successful call of set_area_action."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module.logged_in = True
        page = Mock()
        page.status_code = 200  # OK
        mock_requests.get.return_value = page
        ip_module.set_area_action(1, 'Arm')
        mock_requests.get.assert_called_once()
        mock_requests.get.assert_called_with(
                'http://127.0.0.1/statuslive.html',
                params={'area': '00', 'value': 'r'},
                verify=False
                )


if __name__ == '__main__':
    # This is not useful because the ip150 module will not be found if
    # executed directly.
    # Run `python3 -m unittest` in the root of the repository to run all tests.
    unittest.main()
