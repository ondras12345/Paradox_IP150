#!/usr/bin/env python3

"""Tests for alarm status info parsing."""

import unittest
from unittest.mock import Mock, patch
from ip150 import Paradox_IP150


class TestParsing(unittest.TestCase):
    """Tests for alarm status info parsing."""

    def test_js2array(self):
        """Test if _js2array can properly parse IP150's javascript output."""
        script = """
var hebrew = "0";
tbl_statuszone = new Array(0,0,0,1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);var stayd="0";var option="235";tbl_useraccess = new Array(9,8,0,0);tbl_alarmes = new Array();tbl_troubles = new Array();if(top.mainframe.formframe&& typeof(top.mainframe.formframe.startstatus)!="undefined"){
if (top.menu_currentitem==0){
if(top.mainframe.formframe.startstatus){
top.st_init();
top.savedata(tbl_useraccess, tbl_statuszone, -1, option);
top.mainframe.formframe.document.getElementById('DS').innerHTML = top.st_affdata("Paradox system ", tbl_useraccess, hebrew);
top.st_affallzonealarm();
top.Chargement();
top.mainframe.formframe.st_startblink();
top.mainframe.formframe.startstatus = 0;
}
top.updatedata(tbl_useraccess,tbl_statuszone,stayd,option);
top.lostcom=120;
top.updatedata_al(tbl_alarmes,hebrew);
top.updatedata_tr(tbl_troubles);
setTimeout('window.location.replace("statuslive.html")',2000);
}
}
if (top.subrequest==1){
    top.makesubmit();
}"""
        self.assertEqual(
            Paradox_IP150._js2array('tbl_statuszone', script),
            [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
             0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            )

        self.assertEqual(
            Paradox_IP150._js2array('tbl_useraccess', script),
            [9, 8, 0, 0]
            )

    @patch('ip150.requests')
    def test_get_info(self, mock_requests):
        """Test the get_info function.

        Most it's functionality should already be tested by test_js2array.
        """
        page = Mock()
        page.text = """
<!DOCTYPE HTML PUBLIC '-//W3C//DTD HTML 4.01 Transitional//EN' 'http://www.w3.org/TR/html4/loose.dtd'>
<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
</head>
<body>
<form name="statuslive" action="statuslive.html" method="get">
<input type='hidden' name='area' />
<input type='hidden' name='value'>
</form>
<script type='text/javascript'>var hebrew = "0";
tbl_statuszone = new Array(0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);var stayd="0";var option="235";tbl_useraccess = new Array(9,9,0,0);tbl_alarmes = new Array();tbl_troubles = new Array();if(top.mainframe.formframe&& typeof(top.mainframe.formframe.startstatus)!="undefined"){
if (top.menu_currentitem==0){
if(top.mainframe.formframe.startstatus){
top.st_init();
top.savedata(tbl_useraccess, tbl_statuszone, -1, option);
top.mainframe.formframe.document.getElementById('DS').innerHTML = top.st_affdata("Paradox system ", tbl_useraccess, hebrew);
top.st_affallzonealarm();
top.Chargement();
top.mainframe.formframe.st_startblink();
top.mainframe.formframe.startstatus = 0;
}
top.updatedata(tbl_useraccess,tbl_statuszone,stayd,option);
top.lostcom=120;
top.updatedata_al(tbl_alarmes,hebrew);
top.updatedata_tr(tbl_troubles);
setTimeout('window.location.replace("statuslive.html")',2000);
}
}
if (top.subrequest==1){
    top.makesubmit();
}
</script>
</body>
</html>
"""
        mock_requests.get.return_value = page
        ip_module = Paradox_IP150('http://127.0.0.1')
        ip_module._logged_in = True
        res = ip_module.get_info()
        mock_requests.get.assert_called_once()
        expected_res = {
            'zones_status': [(1, 'Closed'),  (2, 'Closed'),  (3, 'Closed'),
                             (4, 'Closed'),  (5, 'Closed'),  (6, 'Closed'),
                             (7, 'Closed'),  (8, 'Closed'),  (9, 'Closed'),
                             (10, 'Closed'), (11, 'Closed'), (12, 'Closed'),
                             (13, 'Closed'), (14, 'Open'),   (15, 'Closed'),
                             (16, 'Closed'), (17, 'Closed'), (18, 'Closed'),
                             (19, 'Closed'), (20, 'Closed'), (21, 'Closed'),
                             (22, 'Closed'), (23, 'Closed'), (24, 'Closed'),
                             (25, 'Closed'), (26, 'Closed'), (27, 'Closed'),
                             (28, 'Closed'), (29, 'Closed'), (30, 'Closed'),
                             (31, 'Open'),   (32, 'Closed'), (33, 'Closed'),
                             (34, 'Closed'), (35, 'Closed'), (36, 'Closed'),
                             (37, 'Closed'), (38, 'Closed'), (39, 'Closed'),
                             (40, 'Closed'), (41, 'Closed'), (42, 'Closed'),
                             (43, 'Closed'), (44, 'Closed'), (45, 'Closed'),
                             (46, 'Closed'), (47, 'Closed'), (48, 'Closed'),
                             ],
            'areas_status': [(1, 'Not_ready'), (2, 'Not_ready'),
                             (3, 'Unset'), (4, 'Unset')],
        }
        self.assertEqual(res, expected_res)


if __name__ == '__main__':
    # This is not useful because the ip150 module will not be found if
    # executed directly.
    # Run `python3 -m unittest` in the root of the repository to run all tests.
    unittest.main()
