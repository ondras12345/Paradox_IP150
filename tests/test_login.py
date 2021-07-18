#!/usr/bin/env python3

"""Test the login and logout functionality."""

import unittest
from unittest.mock import patch, Mock
from ip150 import Paradox_IP150, Paradox_IP150_Error


class TestLogin(unittest.TestCase):
    """Tests for the login and logout functionality."""

    def test_not_logged_in(self):
        """Test if calling get_info without being logged in raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.get_info()
        self.assertEqual(str(cm.exception),
                         'Not logged in; please use login() first.')

    def test_already_loggen_in(self):
        """Test if calling login twice raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.login('usr', 'pwd')
        self.assertEqual(str(cm.exception),
                         'Already logged in; please use logout() first.')

    @patch('ip150.requests')
    def test_login_wrong_page(self, mock_requests):
        """Test if fetching wrong webpage causes login() to raise an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        lpage = Mock()
        lpage.text = "<html></html>"
        mock_requests.get.return_value = lpage
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.login('1234', 'test')
        self.assertEqual(str(cm.exception),
                         'Wrong page fetched. '
                         'Did you connect to the right server and port? '
                         'Server returned: <html></html>')
        mock_requests.get.assert_called_once()
        mock_requests.get.assert_called_with(
                'http://127.0.0.1/login_page.html',
                verify=False
                )

    @patch('ip150.requests')
    def test_login_wrong_credentials(self, mock_requests):
        """Test if logging in with the wrong credentials raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        page = Mock()
        # loginaff is required to pass the "wrong page" condition.
        # The first parameter of loginaff is the sess salt.
        # top.location... is required to fail with "wrong credentials".
        page.text = ("loginaff(\"7BB0A0C78D08A8CE\", ...); "
                     "top.location.href='login_page.html';")
        mock_requests.get.return_value = page
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.login('1234', 'test')
        self.assertEqual(str(cm.exception),
                         'Could not login, wrong credentials provided.')
        mock_requests.get.assert_called_with(
                'http://127.0.0.1/default.html',
                params={'p': '14A3DD3D3BFD389B272BB5BCD27FF88E',
                        'u': '80815A09'},
                verify=False
                )

    @patch('ip150.requests')
    @patch('ip150.KeepAlive')
    @patch('ip150.time.sleep')  # prevent the test from taking too long
    def test_login_successful(self, mock_time, mock_keepalive, mock_requests):
        """Test a successful login."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        page = Mock()
        # The first parameter of loginaff is the sess salt.
        page.text = """
<script type='text/javascript'>document.getElementById('LOGIN').innerHTML = loginaff("7BB0A0C78D08A8CE",0,"Paradox system ","","user",0);logininit("user");</script>
"""
        mock_requests.get.return_value = page
        ip_module.login('1234', 'test', keep_alive_interval=10.0)
        mock_keepalive.assert_called_with('http://127.0.0.1', 10.0)
        ip_module._keepalive.start.assert_called_once()
        self.assertTrue(ip_module.logged_in)

    @patch('ip150.requests')
    def test_logout_error(self, mock_requests):
        """Test if logout page that does not return 200 OK raises an error."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        _keepalive = Mock()
        ip_module._keepalive = _keepalive
        logout_page = Mock()
        logout_page.status_code = 404  # Page Not Found
        mock_requests.get.return_value = logout_page
        with self.assertRaises(Paradox_IP150_Error) as cm:
            ip_module.logout()
        self.assertEqual(str(cm.exception),
                         'Error logging out')
        mock_requests.get.assert_called_with('http://127.0.0.1/logout.html',
                                             verify=False)
        # _keepalive thread is canceled before the error occurs.
        _keepalive.cancel.assert_called_once()
        _keepalive.join.assert_called_once()
        self.assertIsNone(ip_module._keepalive)
        # We remain logged in, but the _keepalive thread is already canceled.
        # This would most likely cause failure sooner or later.
        self.assertTrue(ip_module.logged_in)

    @patch('ip150.requests')
    def test_logout_successful(self, mock_requests):
        """Test a successful logout."""
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        _keepalive = Mock()
        ip_module._keepalive = _keepalive
        logout_page = Mock()
        logout_page.status_code = 200  # OK
        mock_requests.get.return_value = logout_page
        # _updates must not be None if we want to test that logout() stops it.
        ip_module._updates = Mock()
        ip_module._stop_updates = Mock()
        ip_module.logout()
        mock_requests.get.assert_called_with('http://127.0.0.1/logout.html',
                                             verify=False)
        _keepalive.cancel.assert_called_once()
        _keepalive.join.assert_called_once()
        self.assertIsNone(ip_module._keepalive)
        self.assertIsNone(ip_module._updates)
        ip_module._stop_updates.set.assert_called_once()
        self.assertFalse(ip_module.logged_in)


if __name__ == '__main__':
    # This is not useful because the ip150 module will not be found if
    # executed directly.
    # Run `python3 -m unittest` in the root of the repository to run all tests.
    unittest.main()
