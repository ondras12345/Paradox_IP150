#!/usr/bin/env python3

"""MQTT adapter for IP150 Alarms."""

import ip150
import paho.mqtt.client as mqtt
import argparse
import json
import urllib.parse
import getpass
import logging


_LOGGER = logging.getLogger(__name__)


class IP150_MQTT_Error(Exception):
    """IP150_MQTT Error."""


class IP150_MQTT():
    """Representation of Paradox IP150 MQTT adapter."""

    _status_map = {
        'areas_status': {
            'topic': 'ALARM_PUBLISH_TOPIC',
            'map': {
                'Disarmed':     'disarmed',
                'Armed':        'armed_away',
                'Triggered':    'triggered',
                'Armed_sleep':  'armed_night',
                'Armed_stay':   'armed_home',
                'Entry_delay':  'pending',
                'Exit_delay':   'arming',
                'Ready':        'disarmed'
            }
        },
        'zones_status': {
            'topic': 'ZONE_PUBLISH_TOPIC',
            'map': {
                'Closed':           'off',
                'Open':             'on',
                'In_alarm':         'on',
                'Closed_Trouble':   'off',
                'Open_Trouble':     'on',
                'Closed_Memory':    'off',
                'Open_Memory':      'on',
                'Bypass':           'off',
                'Closed_Trouble2':  'off',
                'Open_Trouble2':    'on'
            }
        }
    }

    _alarm_action_map = {
        'DISARM':       'Disarm',
        'ARM_AWAY':     'Arm',
        'ARM_NIGHT':    'Arm_sleep',
        'ARM_HOME':     'Arm_stay'
        }

    def __init__(self, config):
        """Initialize the IP150 MQTT adapter."""
        self._cfg = config
        self._will = (self._cfg['CTRL_PUBLISH_TOPIC'], 'Disconnected',
                      1, True)

    def _on_paradox_new_state(self, state, client):
        for d1 in state.keys():
            d1_map = self._status_map.get(d1, None)
            if d1_map:
                for d2 in state[d1]:
                    publish_state = d1_map['map'].get(d2[1], None)
                    if publish_state:
                        client.publish(
                                f'{self._cfg[d1_map["topic"]]}/{str(d2[0])}',
                                publish_state, 1, True)

    def _on_paradox_update_error(self, e, client):
        # We try to do a proper shutdown,
        # like if the user asked us to disconnect via MQTT
        _LOGGER.error(f'update error {str(e)}, terminating')
        self.mqtt_ctrl_disconnect(client)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc != 0:
            raise IP150_MQTT_Error(
                    f'Error while connecting to the MQTT broker. '
                    f'Reason code: {str(rc)}')

        client.subscribe([(f'{self._cfg["ALARM_SUBSCRIBE_TOPIC"]}/+', 1),
                          (self._cfg['CTRL_SUBSCRIBE_TOPIC'], 1)])

        client.publish(self._cfg['CTRL_PUBLISH_TOPIC'], 'Connected', 1, True)

        _LOGGER.info('MQTT connected')

        self.ip.get_updates(self._on_paradox_new_state,
                            self._on_paradox_update_error, client)

    def _on_mqtt_alarm_message(self, client, userdata, message):
        # Parse area number
        area = message.topic.rpartition('/')[2]
        if area.isdigit():
            action = self._alarm_action_map.get(message.payload.decode(), None)
            if action:
                if self._cfg['READ_ONLY']:
                    _LOGGER.info(f'Action "{action}" ignored (READ_ONLY)')
                else:
                    self.ip.set_area_action(area, action)

    def mqtt_ctrl_disconnect(self, client):
        """Disconnect from the MQTT broker and the IP150 and terminate."""
        _LOGGER.info('mqtt_ctrl_disconnect called')
        self.ip.cancel_updates()
        client.publish(*self._will)
        client.disconnect()
        self.ip.logout()

    def _on_mqtt_ctrl_message(self, client, userdata, message):
        switcher = {
            'Disconnect': self.mqtt_ctrl_disconnect
        }

        func = switcher.get(message.payload.decode(), None)
        if func:
            return func(client)

    def _parse_mqtt_url(self):
        parsed = urllib.parse.urlsplit(self._cfg['MQTT_ADDRESS'])
        port = parsed.port
        if not port:
            if parsed.scheme == 'mqtt':
                port = 1883
            elif parsed.scheme == 'mqtts':
                port = 8883
            else:
                raise IP150_MQTT_Error(
                        'No port defined, nor "mqtt" nor "mqtts" scheme.')
            _LOGGER.info(f'Defaulting to MQTT port {port} ({parsed.scheme})')
        return (parsed.hostname, port)

    def loop_forever(self):
        """Start the adapter.

        This is a blocking call.
        """
        mqtt_hostname, mqtt_port = self._parse_mqtt_url()

        self.ip = ip150.Paradox_IP150(self._cfg['IP150_ADDRESS'])
        self.ip.login(self._cfg['PANEL_CODE'], self._cfg['PANEL_PASSWORD'])

        mqc = mqtt.Client()
        mqc.on_connect = self._on_mqtt_connect
        mqc.message_callback_add(f'{self._cfg["ALARM_SUBSCRIBE_TOPIC"]}/+',
                                 self._on_mqtt_alarm_message)
        mqc.message_callback_add(self._cfg['CTRL_SUBSCRIBE_TOPIC'],
                                 self._on_mqtt_ctrl_message)
        mqc.username_pw_set(self._cfg['MQTT_USERNAME'],
                            self._cfg['MQTT_PASSWORD'])
        mqc.will_set(*self._will)

        mqc.connect(mqtt_hostname, mqtt_port)

        mqc.loop_forever()


if __name__ == '__main__':
    argp = argparse.ArgumentParser(description='MQTT adapter for IP150 Alarms')

    argp.add_argument('--getpass-ip150', action='store_true',
                      help='Interactively ask for PANEL_PASSWORD and '
                           'PANEL_CODE. This overrides whatever is stored in '
                           'the config file. Can be used to avoid storing '
                           'credentials to disk when used outside of '
                           'Home Assistant')

    argp.add_argument('--read-only', action='store_true',
                      help='Disallow control through MQTT. '
                           'Overrides READ_ONLY in config file.')

    argp.add_argument('--debug', action='store_true',
                      help='Log DEBUG level messages')

    argp.add_argument('config', type=argparse.FileType(),
                      default='options.json', nargs='?')

    args = argp.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        _LOGGER.info('Logging DEBUG level messages')
    else:
        logging.basicConfig(level=logging.INFO)

    with args.config:
        _LOGGER.debug(f'Loading config from {args.config.name}')
        config = json.load(args.config)

    if args.read_only:
        config['READ_ONLY'] = True

    if config['READ_ONLY']:
        _LOGGER.info('Starting in read-only mode')

    if args.getpass_ip150:
        config['PANEL_PASSWORD'] = getpass.getpass(prompt="PANEL_PASSWORD: ")
        config['PANEL_CODE'] = getpass.getpass(prompt="PANEL_CODE: ")

    _LOGGER.debug(f'Starting with config {repr(config)}')
    ip_mqtt = IP150_MQTT(config)
    ip_mqtt.loop_forever()
