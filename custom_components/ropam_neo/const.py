"""Stałe integracji Ropam Neo."""

DOMAIN = "ropam_neo"
MANUFACTURER = "Ropam Elektronik"

CONF_DEVICE_ID = "device_id"
CONF_TCP_KEY = "tcp_key"
CONF_USER_CODE = "user_code"
CONF_PANIC_BUTTON = "panic_button"
CONF_FIRE_BUTTON = "fire_button"
CONF_Z1_SENSORS = "zone1_sensors"
CONF_Z1_DELAY = "zone1_delay"
CONF_Z1_ACTION = "zone1_action"

DEFAULT_PORT = 9999
SETUP_TIMEOUT = 25

PANEL_URL_PATH = "ropam-neo"
PANEL_STATIC_URL = "/ropam_neo_static"
PANEL_JS = "ropam-neo-panel.js"
PANEL_ELEMENT = "ropam-neo-panel"

EVENT_MESSAGE = "ropam_neo_message"

PLATFORMS = ["alarm_control_panel", "binary_sensor", "button", "sensor", "switch"]

VERSION = "1.4"
