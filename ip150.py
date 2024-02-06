"""Support for Paradox IP150 alarm IP module."""
import hashlib
import requests
import time
import threading
from bs4 import BeautifulSoup
import re
import json
import functools
import logging


_LOGGER = logging.getLogger(__name__)


class Paradox_IP150_Error(Exception):
    """Paradox IP150 error."""


class KeepAlive(threading.Thread):
    """Thread that periodically sends keepalives to the Paradox IP150."""

    def __init__(self, ip150url, interval):
        """Initialize the KeepAlive thread."""
        threading.Thread.__init__(self, daemon=True)
        self.ip150url = ip150url
        self.interval = interval
        self.stopped = threading.Event()

    def _one_keepalive(self):
        requests.get(f'{self.ip150url}/keep_alive.html', params={'msgid': 1},
                     verify=False)

    def run(self):
        """Periodically send keepalives until stopped."""
        while not self.stopped.wait(self.interval):
            self._one_keepalive()

    def cancel(self):
        """Stop sending keepalives."""
        self.stopped.set()


class Paradox_IP150:
    """Representation of Paradox IP150 module."""

    _tables_map = {
        # A map from human readable info about the alarm, to "table" (in fact,
        # array) names used in IP150 software

        # Redundant list of zones with an alarm currently triggered. A zone in
        # alarm will also be reported in the 'tbl_useraccess' table
        # 'triggered_alarms': 'tbl_alarmes',

        # Could use this list to publish alarm troubles, not required for now
        # 'troubles': 'tbl_troubles',

        # The next list provides the status (0=Closed, 1=Open) for each zone
        'zones_status': {
            'name': 'tbl_statuszone',
            'map': {
                0: 'Closed',
                1: 'Open',
                2: 'In_alarm',
                3: 'Closed_Trouble',
                4: 'Open_Trouble',
                5: 'Closed_Memory',
                6: 'Open_Memory',
                7: 'Bypass',
                8: 'Closed_Trouble2',
                9: 'Open_Trouble2'
            }
        },
        # The next list provides the status (as an integer, 0 for area not
        # enabled) for each supported area
        'areas_status': {
            'name': 'tbl_useraccess',
            'map': {
                0: 'Unset',
                1: 'Disarmed',
                2: 'Armed',
                3: 'Triggered',
                4: 'Armed_sleep',
                5: 'Armed_stay',
                6: 'Entry_delay',
                7: 'Exit_delay',
                8: 'Ready',
                9: 'Not_ready',
                10: 'Instant'
            }
        }
    }

    _areas_action_map = {
        # Mappring from human readable commands to machine readable
        'Disarm':       'd',
        'Arm':          'r',
        'Arm_sleep':    'p',
        'Arm_stay':     's'
    }

    def __init__(self, ip150url):
        """Initialize the IP150 module."""
        self.ip150url = ip150url
        self._logged_in = False
        self._keepalive = None
        self._updates = None
        self._stop_updates = threading.Event()

    @property
    def logged_in(self):
        """See if we are logged in to the IP150 module.

        This does not actually check anything with the IP150 module,
        it just returns the value of an internal variable.
        """
        return self._logged_in

    def _logged_only(f):
        @functools.wraps(f)
        def wrapped(self, *args, **kwargs):
            if not self._logged_in:
                raise Paradox_IP150_Error(
                    'Not logged in; please use login() first.')
            else:
                return f(self, *args, **kwargs)
        return wrapped

    @staticmethod
    def _to_8bits(s):
        return "".join(map(lambda x: chr(ord(x) % 256), s))

    @staticmethod
    def _paradox_rc4(data, key):
        """Return the result of Paradox's non-standard RC4."""
        S = list(range(256))
        j = 0
        out = []

        # This is not standard RC4
        for i in range(len(key) - 1, -1, -1):
            j = (j + S[i] + ord(key[i])) % 256
            S[i], S[j] = S[j], S[i]

        i = j = 0
        # This is not standard RC4
        for ch in data:
            i = i % 256
            j = (j + S[i]) % 256
            S[i], S[j] = S[j], S[i]
            out.append(ord(ch) ^ S[(S[i] + S[j]) % 256])
            i += 1

        _LOGGER.debug(f'_paradox_rc4({repr(data)}, {repr(key)}): {repr(out)}')
        return "".join(map(lambda x: '{0:02X}'.format(x), out))

    @staticmethod
    def _prep_cred(user, pwd, sess):
        """Compute salted credentials in preparation for login.

        Returns params for requests.get().
        """
        pwd_8bits = Paradox_IP150._to_8bits(pwd)
        pwd_md5 = hashlib.md5(pwd_8bits.encode('ascii')).hexdigest().upper()
        spass = pwd_md5 + sess
        return {'p': hashlib.md5(spass.encode('ascii')).hexdigest().upper(),
                'u': Paradox_IP150._paradox_rc4(user, spass)}

    def login(self, user, pwd, keep_alive_interval=5.0):
        """Log in to the IP150 module and start sending keepalives."""
        if self.logged_in:
            raise Paradox_IP150_Error(
                'Already logged in; please use logout() first.')

        # Ask for a login page, to get the 'sess' salt
        lpage = requests.get(f'{self.ip150url}/login_page.html', verify=False)

        # Extract the 'sess' salt
        off = lpage.text.find('loginaff')
        if off == -1:
            raise Paradox_IP150_Error(
                f'Wrong page fetched. '
                f'Did you connect to the right server and port? '
                f'Server returned: {lpage.text}')
        sess = lpage.text[off + 10:off + 26]
        _LOGGER.debug(f'sess salt is {repr(sess)}')

        # Compute salted credentials and do the login
        creds = self._prep_cred(user, pwd, sess)
        defpage = requests.get(f'{self.ip150url}/default.html', params=creds,
                               verify=False)
        if defpage.text.count("top.location.href='login_page.html';") > 0:
            # They're redirecting us to the login page; credentials didn't work
            raise Paradox_IP150_Error(
                'Could not login, wrong credentials provided.')

        # Give enough time to the server to set up.
        time.sleep(3)
        if keep_alive_interval:
            self._keepalive = KeepAlive(self.ip150url, keep_alive_interval)
            self._keepalive.start()
        self._logged_in = True
        _LOGGER.info('login successful')

    @_logged_only
    def logout(self):
        """Log out of the IP150 module.

        Stops sending keepalives and stops the _updates thread if it is
        running.
        """
        if self._keepalive is not None:
            self._keepalive.cancel()
            self._keepalive.join()
            self._keepalive = None
        if self._updates is not None:
            self._stop_updates.set()
            self._updates = None
        logout = requests.get(f'{self.ip150url}/logout.html', verify=False)
        if logout.status_code != 200:
            raise Paradox_IP150_Error('Error logging out')
        self._logged_in = False
        _LOGGER.info('logout successful')

    @staticmethod
    def _js2array(varname, script):
        _LOGGER.debug(f'_js2array({repr(varname)}, {repr(script)})')
        res = re.search(r'{} = new Array\((.*?)\);'.format(varname), script)
        res = f'[{res.group(1)}]'
        _LOGGER.debug(f'Resulting JSON: {repr(res)}')
        return json.loads(res)

    @_logged_only
    def get_info(self, timeout=0.9):
        """Get and parse status info from statuslive.html."""
        try:
            status_page = requests.get(f'{self.ip150url}/statuslive.html',
                                       verify=False, timeout=timeout)
        except requests.exceptions.Timeout:
            raise Paradox_IP150_Error('Could not retrieve status information: timeout')
        status_parsed = BeautifulSoup(status_page.text, 'html.parser')
        if status_parsed.find('form', attrs={'name': 'statuslive'}) is None:
            raise Paradox_IP150_Error('Could not retrieve status information')
        script = status_parsed.find('script').string
        _LOGGER.debug(f'statuslive script: {repr(script)}')
        res = {}
        for table in self._tables_map.keys():
            # Extract the js array for the current "table"
            tmp = self._js2array(self._tables_map[table]['name'], script)
            # Map the extracted machine values to the corresponding human
            # values
            res[table] = [(i, self._tables_map[table]['map'][x]) for i, x in enumerate(tmp, start=1)]
        return res

    def _get_updates(self, on_update, on_error, userdata, interval, max_retry_count=5):
        """Periodically fetch updates from the IP150.

        This is the body of the _updates thread.
        """
        try:
            prev_state = {}
            retry_count = 0

            while not self._stop_updates.wait(interval):
                try:
                    cur_state = self.get_info()
                except Paradox_IP150_Error as e:
                    retry_count += 1
                    if retry_count > max_retry_count:
                        raise Paradox_IP150_Error("Max retry count exceeded")
                    else:
                        _LOGGER.warning("get_info failed, retrying", exc_info=e)
                        continue
                else:
                    retry_count = 0

                updated_state = {}
                for d1 in cur_state.keys():
                    if d1 in prev_state:
                        for cur_d2, prev_d2 in zip(cur_state[d1],
                                                   prev_state[d1]):
                            if cur_d2 != prev_d2:
                                if d1 in updated_state:
                                    updated_state[d1].append(cur_d2)
                                else:
                                    updated_state[d1] = [cur_d2]
                    else:
                        updated_state[d1] = cur_state[d1]

                if len(updated_state) > 0:
                    on_update(updated_state, userdata)

                prev_state = cur_state
        except Exception as e:
            # The thread will terminate, but cancel_updates will have to be
            # called to clean up the mess before get_updates can be called
            # again.
            if on_error:
                on_error(e, userdata)
        finally:
            self._stop_updates.clear()

    @_logged_only
    def get_updates(self, on_update=None, on_error=None, userdata=None,
                    poll_interval=1.0):
        """Start the _updates thread."""
        if not on_update:
            raise Paradox_IP150_Error(
                    'The callable on_update must be provided.')
        if poll_interval <= 0.0:
            raise Paradox_IP150_Error(
                    'The polling interval must be greater than 0.0 seconds.')
        if self._updates is not None:
            raise Paradox_IP150_Error('Already getting updates.')
        self._updates = threading.Thread(target=self._get_updates,
                                         args=(on_update, on_error, userdata,
                                               poll_interval),
                                         daemon=True)
        self._updates.start()
        _LOGGER.info(f'_updates thread started ({poll_interval} s)')

    @_logged_only
    def cancel_updates(self):
        """Stop the _updates thread."""
        if self._updates is not None:
            self._stop_updates.set()
            self._updates = None
            _LOGGER.info('_updates thread stopped')
        else:
            raise Paradox_IP150_Error(
                'Not currently getting updates. Use get_updates() first.')

    @_logged_only
    def set_area_action(self, area, action):
        """Perform action (arm, disarm, ...) on specified area."""
        if isinstance(area, str):
            area = int(area)
        area -= 1
        if area < 0:
            raise Paradox_IP150_Error('Invalid area provided.')
        if action not in self._areas_action_map:
            raise Paradox_IP150_Error(
                f'Invalid action "{action}" provided. '
                f'Valid actions are {list(self._areas_action_map.keys())}')
        action = self._areas_action_map[action]
        # This will seem off-by-one compared to the passed argument (area -= 1)
        _LOGGER.info(f'Performing action "{action}" on area {area:02d}')
        act_res = requests.get(f'{self.ip150url}/statuslive.html',
                               params={'area': f'{area:02d}',
                                       'value': action},
                               verify=False)
        if act_res.status_code != 200:
            raise Paradox_IP150_Error('Error setting the area action')
