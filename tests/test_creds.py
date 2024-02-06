#!/usr/bin/env python3

"""Tests for Paradox IP150 credential encoding."""

import unittest
from ip150 import Paradox_IP150


class TestParadoxRC4(unittest.TestCase):
    """Tests for Paradox's non-standard RC4."""

    def test_rc4_valid(self):
        """Test if RC4 works with valid input data."""
        data = '1234'
        key = '098F6BCD4621D373CADE4E832627B4F67BB0A0C78D08A8CE'
        res = Paradox_IP150._paradox_rc4(data, key)
        self.assertEqual(res, '80815A09')


class TestParadoxCreds(unittest.TestCase):
    """Tests for Paradox IP150 credential encoding."""

    def test_creds_valid(self):
        """Test if _prep_cred works with valid input data."""
        PANEL_CODE = '1234'
        PANEL_PASSWORD = 'test'
        sess = '7BB0A0C78D08A8CE'
        res = Paradox_IP150._prep_cred(PANEL_CODE, PANEL_PASSWORD, sess)
        self.assertEqual(res, {'p': '14A3DD3D3BFD389B272BB5BCD27FF88E',
                               'u': '80815A09'})


if __name__ == '__main__':
    # This is not useful because the ip150 module will not be found if
    # executed directly.
    # Run `python3 -m unittest` in the root of the repository to run all tests.
    unittest.main()
