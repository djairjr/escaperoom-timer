#!/usr/bin/env bash
# timer-watcher.sh - root side of the web configurator's sandbox.
#
# The web server runs as $TIMER_USER and only writes requests under /sandbox; this loop (root, systemd)
# applies them:
#   /sandbox/config/config.json  -> /etc/timer-sdl/config.json, then restart timer-sdl
#   /sandbox/sfx/<file>          -> /var/lib/timer-nicolau/sfx/<file>
#   /sandbox/wifi/connect        -> "SSID|PASSWORD": join that network on the client interface
#   /sandbox/wifi/ap_on|ap_off   -> start/stop timer-ap.service
#   /sandbox/wifi/scan_request   -> scan on the client interface, answer in scan_cache.json
#   /sandbox/reload/timer-sdl    -> restart timer-sdl
#
# A failing request is logged and dropped; it never stops the loop (with `set -e`, one stale
# request would kill it on every restart and block everything queued behind it).
set -u
LOG_TAG=timer-watcher
# shellcheck source=/usr/lib/timer-nicolau/common.sh
. /usr/lib/timer-nicolau/common.sh

SANDBOX=/sandbox
POLL_INTERVAL=2

restart_timer() {
    systemctl restart "$TIMER_SERVICE" && log "timer restarted" || log "timer restart failed"
}

apply_config() {
    local f="$SANDBOX/config/config.json"
    [ -f "$f" ] || return 0
    if python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" 2>/dev/null; then
        install -o root -g root -m 644 "$f" "$CONFIG_JSON" && log "config applied"
        restart_timer
    else
        log "config rejected: invalid JSON"
    fi
    rm -f "$f"
}

apply_sfx() {
    local f moved=0
    shopt -s nullglob
    for f in "$SANDBOX/sfx/"*; do
        [ -f "$f" ] || continue
        case "${f,,}" in
            *.mp3|*.wav|*.ogg|*.flac)
                mv -f "$f" "$SFX_DIR/$(basename "$f")" && moved=1 && log "sound: $(basename "$f")" ;;
            *)
                log "sound rejected: $(basename "$f")"; rm -f "$f" ;;
        esac
    done
    shopt -u nullglob
    [ "$moved" = 1 ] && chown -R "$TIMER_USER:$TIMER_USER" "$SFX_DIR"
}

wifi_connect() {
    local f="$SANDBOX/wifi/connect" content ssid pass result
    [ -f "$f" ] || return 0
    content=$(cat "$f")
    rm -f "$f"
    ssid=${content%%|*}
    pass=${content#*|}
    [ "$pass" = "$content" ] && pass=""
    log "wifi: joining '$ssid'"
    result=$(/usr/lib/timer-nicolau/timer-wifi-connect "$ssid" "$pass" 2>&1 | tail -1)
    log "wifi: $result"
    printf '%s|%s\n' "$ssid" "$result" > "$SANDBOX/wifi/connect_result"
    chown "$TIMER_USER:$TIMER_USER" "$SANDBOX/wifi/connect_result"
}

ap_requests() {
    if [ -f "$SANDBOX/wifi/ap_on" ]; then
        rm -f "$SANDBOX/wifi/ap_on"
        systemctl start timer-ap.service && log "access point started on request" || log "access point failed to start"
    fi
    if [ -f "$SANDBOX/wifi/ap_off" ]; then
        rm -f "$SANDBOX/wifi/ap_off"
        systemctl stop timer-ap.service && log "access point stopped on request"
    fi
    # Older web clients sent their own hostapd/dnsmasq files; the access point is configured by
    # timer-ap, so they are dropped.
    rm -f "$SANDBOX/ap/hostapd.conf" "$SANDBOX/ap/dnsmasq.conf"
}

reload_requests() {
    if [ -f "$SANDBOX/reload/timer-sdl" ]; then
        rm -f "$SANDBOX/reload/timer-sdl"
        restart_timer
    fi
    rm -f "$SANDBOX/reload/hostapd" "$SANDBOX/reload/dnsmasq"
}

wifi_scan() {
    [ -f "$SANDBOX/wifi/scan_request" ] || return 0
    rm -f "$SANDBOX/wifi/scan_request"
    # Written aside and renamed: the web server polls for scan_cache.json and would otherwise
    # read the empty file the shell creates before the scan ends.
    local tmp="$SANDBOX/wifi/.scan_cache.tmp"
    /usr/lib/timer-nicolau/timer-wifi-scan > "$tmp" 2>/dev/null || echo '[]' > "$tmp"
    chown "$TIMER_USER:$TIMER_USER" "$tmp"
    mv -f "$tmp" "$SANDBOX/wifi/scan_cache.json"
    log "wifi scan: $(grep -o '"ssid"' "$SANDBOX/wifi/scan_cache.json" | wc -l) networks"
}

log "watching $SANDBOX every ${POLL_INTERVAL}s (client=$CLIENT_IFACE ap=$AP_IFACE)"
mkdir -p "$SANDBOX"/{config,sfx,wifi,ap,reload}
chown "$TIMER_USER:$TIMER_USER" "$SANDBOX" "$SANDBOX"/{config,sfx,wifi,ap,reload}

while true; do
    if [ -n "$(find "$SANDBOX" -maxdepth 2 -type f ! -name scan_cache.json ! -name connect_result 2>/dev/null | head -1)" ]; then
        apply_config
        apply_sfx
        ap_requests
        wifi_connect
        wifi_scan
        reload_requests
    fi
    sleep "$POLL_INTERVAL"
done
