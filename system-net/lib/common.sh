# Shared settings and helpers for the timer-nicolau network and SD tools.
# Sourced, never executed. Values come from /etc/timer-nicolau/net.conf; these are the defaults.

ETH_IFACE=end0
AP_IFACE=wlan0
CLIENT_IFACE=wlan1
AP_ADDR=192.168.4.1
AP_PREFIX=Nicolau
AP_CHANNEL=6
# Empty: use http_password from the web configurator's setup.json, so the AP and the web login
# share the one password the client already knows.
AP_PASSPHRASE=
# Seconds, at boot without a cable, to wait for the Wi-Fi client before the access point comes up.
BOOT_WAIT=20
SETUP_JSON=/opt/puzzle-configurator/setup.json
CONFIG_JSON=/etc/timer-sdl/config.json
SFX_DIR=/var/lib/timer-nicolau/sfx
# System user (no login) that runs the web configurator and owns the sounds and the sandbox.
TIMER_USER=timersdl
TIMER_SERVICE=timer-sdl.service
WPA_CONF_DIR=/etc/wpa_supplicant

# shellcheck disable=SC1091
[ -r /etc/timer-nicolau/net.conf ] && . /etc/timer-nicolau/net.conf

RUN_DIR=/run/timer-nicolau

log() { echo "$(date '+%F %T') [${LOG_TAG:-timer-nicolau}] $*"; }
die() { log "ERROR: $*"; exit 1; }

# SSID "<prefix>-XXXX", XXXX = last four hex digits of the AP interface MAC (as the web configurator shows).
ap_ssid() {
    local mac
    mac=$(cat "/sys/class/net/$AP_IFACE/address" 2>/dev/null || echo "00:00")
    echo "${AP_PREFIX}-$(echo "$mac" | tr -d ':' | tail -c 5 | tr '[:lower:]' '[:upper:]')"
}

ap_passphrase() {
    if [ -n "$AP_PASSPHRASE" ]; then
        echo "$AP_PASSPHRASE"
    elif [ -r "$SETUP_JSON" ]; then
        python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("http_password", ""))' "$SETUP_JSON"
    fi
}

has_default_route() { [ -n "$(ip -4 route show default 2>/dev/null)" ]; }
