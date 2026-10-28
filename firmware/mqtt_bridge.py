#!/usr/bin/env python3
"""MQTT Bridge for Timer-Nicolau - simplest possible."""
import paho.mqtt.client as mqtt
import sys, os, signal, threading, time, json, subprocess

STDOUT = sys.stdout.fileno()

def out(msg):
    os.write(STDOUT, (msg + "\n").encode())
    try:
        os.fsync(STDOUT)
    except OSError:
        pass

cfg_p = "/tmp/timer_mqtt_config.json"
if os.path.exists(cfg_p):
    with open(cfg_p) as f:
        cfg = json.load(f)
else:
    cfg = {"room": "SALA A", "prefix": "nicolau/timer/SALA A", "ha_prefix": "homeassistant"}

import subprocess
HOSTNAME = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip() or "orange-pi"
ROOM = cfg["room"]
U = ROOM.replace(" ", "_") + "_" + HOSTNAME
PREFIX = cfg["prefix"]
HA = cfg.get("ha_prefix", "homeassistant")
# Connection settings come from config.json through timer-sdl (MQTTClient::init).
BROKER = cfg.get("broker", "")
PORT = int(cfg.get("port") or 1883)
USER = cfg.get("username", "")
PASS = cfg.get("password", "")
if not BROKER:
    out("bridge: no mqtt_broker configured; exiting")
    sys.exit(0)
CMDFILE = "/tmp/timer_mqtt.cmd"
client = None

def on_connect(c, userdata, flags, rc):
    out(f"connected|{rc}")
    for t in ["/command", "/disarmed/set", "/config_update", "/volume/set", "/duration/set", "/trap/set"]:
        c.subscribe(PREFIX + t, qos=1)
    # Discovery
    d = f'"device":{{"name":"{HOSTNAME}","identifiers":["nicolau_timer_{U}"]}}'
    h, b = HA, PREFIX
    def p(t, msg):
        c.publish(t, msg, qos=1, retain=True)
    p(h+"/sensor/nicolau_timer_"+U+"_state/config", f'{{"name":"Estado","state_topic":"{b}/state","icon":"mdi:timer","unique_id":"nicolau_timer_{U}_state",{d}}}')
    p(h+"/sensor/nicolau_timer_"+U+"_remaining/config", f'{{"name":"Tempo","unit_of_measurement":"s","state_topic":"{b}/time_remaining","device_class":"duration","icon":"mdi:timer-outline","unique_id":"nicolau_timer_{U}_remaining",{d}}}')
    p(h+"/sensor/nicolau_timer_"+U+"_speed/config", f'{{"name":"Velocidade","unit_of_measurement":"x","state_topic":"{b}/speed_multiplier","icon":"mdi:speedometer","unique_id":"nicolau_timer_{U}_speed",{d}}}')
    p(h+"/button/nicolau_timer_"+U+"_start/config", f'{{"name":"Iniciar","command_topic":"{b}/command","payload_press":"start","icon":"mdi:play","unique_id":"nicolau_timer_{U}_button_start",{d}}}')
    p(h+"/button/nicolau_timer_"+U+"_stop/config", f'{{"name":"Parar","command_topic":"{b}/command","payload_press":"stop","icon":"mdi:stop","unique_id":"nicolau_timer_{U}_button_stop",{d}}}')
    p(h+"/button/nicolau_timer_"+U+"_reset/config", f'{{"name":"Reset","command_topic":"{b}/command","payload_press":"reset","icon":"mdi:restart","unique_id":"nicolau_timer_{U}_button_reset",{d}}}')
    p(h+"/switch/nicolau_timer_"+U+"_disarmed/config", f'{{"name":"Desarmado","state_topic":"{b}/disarmed","command_topic":"{b}/disarmed/set","icon":"mdi:lock-open-variant","unique_id":"nicolau_timer_{U}_disarmed",{d}}}')
    p(h+"/switch/nicolau_timer_"+U+"_trap/config", f'{{"name":"TIME_TRAP","state_topic":"{b}/trap","command_topic":"{b}/trap/set","icon":"mdi:hand-back-right","unique_id":"nicolau_timer_{U}_trap",{d}}}')
    p(h+"/number/nicolau_timer_"+U+"_volume/config", f'{{"name":"Volume","state_topic":"{b}/volume","command_topic":"{b}/volume/set","min":0,"max":128,"step":1,"icon":"mdi:volume-high","unique_id":"nicolau_timer_{U}_volume",{d}}}')
    p(h+"/number/nicolau_timer_"+U+"_duration/config", f'{{"name":"Duracao (s)","state_topic":"{b}/duration","command_topic":"{b}/duration/set","min":60,"max":7200,"step":60,"icon":"mdi:timer-outline","unique_id":"nicolau_timer_{U}_duration",{d}}}')
    # Clean old button_trap discovery
    p(h+"/button/nicolau_timer_"+U+"_button_trap/config", "")
    out("init_states|done")

def on_message(c, userdata, msg):
    os.write(STDOUT, f"{msg.topic}|{msg.payload.decode()}\n".encode())
    try:
        os.fsync(STDOUT)
    except OSError:
        pass

def cmd_reader():
    while True:
        try:
            if os.path.exists(CMDFILE):
                with open(CMDFILE, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line or not client: continue
                        parts = line.split("|")
                        if len(parts) >= 3:
                            client.publish(parts[1], parts[2], qos=1, retain=len(parts)>3 and parts[3]=="1")
                open(CMDFILE, "w").close()
        except: pass
        time.sleep(0.02)

signal.signal(signal.SIGINT, lambda *a: sys.exit(0))
signal.signal(signal.SIGTERM, lambda *a: sys.exit(0))
open(CMDFILE, "a").close()
os.chmod(CMDFILE, 0o666)
out("bridge start")

c = mqtt.Client(client_id="timer-bridge-"+U, clean_session=True, protocol=mqtt.MQTTv311)
c.username_pw_set(USER, PASS)
c.on_connect = on_connect
c.on_message = on_message
client = c

threading.Thread(target=cmd_reader, daemon=True).start()
c.connect(BROKER, PORT, keepalive=30)
c.loop_forever()
