# Escape Room Countdown Timer - Wifi Configurable

A bomb-style countdown timer for escape rooms. It runs on an **Orange Pi PC Plus** (Armbian,
Debian 13 trixie, armhf), draws the countdown full screen on an HDMI TV, plays sounds, reads four
buttons wired into the room and closes a relay when the players win. A game master can also drive
it from Home Assistant over MQTT.

## The game

The players see a large seven-segment countdown (default 60:00) whose colour changes as time runs
out. Four buttons are wired to the board:

| Button | Wire | Who presses it | Role |
|---|---|---|---|
| START | green | game master | starts the countdown; after a game, returns to the ready screen |
| A | yellow | players | one of two identical buttons in the room |
| B | blue | players | the other identical button |
| STOP / DISARM | red | players (hidden in the room) | defuses the bomb: the players win |

**A and B look the same, but the first one pressed decides their roles.** That is the trick of the
room:

1. **Ready.** The screen shows the room name and the idle message ("AMBIENTE SEGURO"); background
   music plays. START begins the game.
2. **Counting at 1x.** One second of countdown per real second, with a tick each second.
3. **The first of A/B pressed becomes ROUBO (robbery).** The display freezes for `trap_pause_seconds`
   (default 3 s) with an alarm, then the countdown runs at `accel_multiplier` times the normal speed
   (default 2x), with a red "2x" (or "3x", ...) on screen.
   The other button becomes the **TIME TRAP**.
4. **TIME TRAP.** While a player *holds* the trap button the countdown slows back to **1x** (green
   "1x" on screen). Releasing it returns to 2x. Holding it is the only way to slow the bomb down.
5. **Win: STOP/DISARM.** Pressed at any time during the game, it stops the countdown, shows the
   victory message ("ACESSO LIBERADO") flashing, plays the victory sound and drives the output
   **high** (relay, magnetic lock, siren, lights).
6. **Lose: time runs out.** The screen shows the game-over message ("BOMBA EXPLODIU") and the
   explosion sound plays; the output stays low.
7. **Back to ready.** After the victory/game-over sound ends, START (or a reset from Home Assistant)
   returns to the ready screen; otherwise it does so by itself after `victory_timeout_sec`.

Internally this is one state machine in `firmware/src/main.cpp`:
`IDLE -> RUNNING_1x -> PAUSE_INITIAL -> RUNNING_2x <-> TRAP_HELD -> SOLVED | GAME_OVER -> IDLE`
(`RUNNING_2x` is the accelerated state, whatever the factor).

## Wiring

Buttons connect a GPIO pin to ground (internal pull-ups, active low). Pins of the 40-pin header:

| Function | GPIO (gpiochip0 line) | Header pin |
|---|---|---|
| START | PC0 (64) | 19 |
| A | PC1 (65) | 21 |
| B | PC2 (66) | 23 |
| STOP / DISARM | PC3 (67) | 24 |
| Output (high on victory) | PA21 (21) | 26 |
| Ground | - | 20, 25, 30 |

`journalctl -u timer-sdl -f` on the board logs every state change, which is the quickest way to
check the buttons.

## Configuring the board

> **The board's own Wi-Fi access point is the way to configure it.** It is up whenever the board is
> not connected to a Wi-Fi network - **including when the Ethernet cable is plugged in** - so a phone
> is all you need; no router or network at the site.

1. Power the board. The network `Nicolau-XXXX` (XXXX = last digits of its Wi-Fi MAC) appears within
   seconds with the cable plugged in, or after 20 s without it if the saved Wi-Fi did not connect.
2. Join it from a phone. Password: the web configurator's (default `timersdl1234!` - change it).
3. Open `http://192.168.4.1` (any address leads there), log in with the same password and edit the
   settings, upload sounds or pick the venue's Wi-Fi network. The access point turns itself off once
   the board is connected to that Wi-Fi.

The access point never interferes with the game: it runs in its own services and the timer does not
wait for it.

## Configuration

`/etc/timer-sdl/config.json`. The fields the firmware uses:

| Field | Meaning |
|---|---|
| `timer_duration_sec` | length of a game (3600 = 60 min) |
| `accel_multiplier` | robbery speed, 1-10 (default 2) |
| `trap_pause_seconds` | freeze after the first of A/B, 0-30 s (default 3) |
| `victory_timeout_sec` | seconds on the victory/game-over screen before returning to ready |
| `room_name`, `idle_message`, `victory_message`, `game_over_message` | screen texts (`\n` breaks a line) |
| `brightness_pct` | display brightness |
| `sounds_enabled`, `custom_sounds_enabled`, `background_music_enabled`, `sound_volume` (0-128) | audio |
| `sound_files.*` | tick, alarm (start of 2x), victory, button press, game over (`penalty_alarm`), background music |
| `gpio_out_desarmado.line`, `.active_high` | victory output line (default 21 = PA21, pin 26) and polarity |
| `mqtt_broker`, `mqtt_port`, `mqtt_username`, `mqtt_password`, `mqtt_topic_prefix`, `ha_discovery_prefix` | Home Assistant connection; empty broker = no MQTT |
| `log_verbosity` | 0-3 |

The game has no time penalty by design: `penalty_seconds`, left in older files, is ignored.

There are three ways to change the configuration, all of which end in the same file:

- **Web configurator** - through the board's own access point (see above, the main way) or
  `http://<board>/` on the local network. Password protected. Also uploads sounds and joins Wi-Fi
  networks.
- **SD card** - a folder with `config.json`, optional `sfx/` and optional `wifi.json`, prepared by
  hand or with the Windows configurator (`configurator-windows/`). Insert it with the board off and
  power on; the result is written back to the card as `TIMER-NICOLAU-RESULTADO.txt`.
  Details: [docs/sd-card-package.md](docs/sd-card-package.md).
- **Home Assistant** - duration and volume (below).

## Network

- **Cable first.** With the Ethernet cable in, the board uses it and keeps Wi-Fi off.
- **Wi-Fi.** Without cable, the board joins the saved Wi-Fi network (set from the web configurator
  or `wifi.json` on the SD card).
- **Configuration access point.** Up unless the board is on a Wi-Fi network: at once with the cable
  plugged in at boot, after 20 s without a cable if no Wi-Fi connected. It goes off once the Wi-Fi
  client has held an address for 30 s; plugging the cable in later brings it back if there is no
  Wi-Fi. See [Configuring the board](#configuring-the-board).

The timer runs the same with or without any network.

## Display

On start the firmware picks the best progressive mode the TV reports (largest, up to 1920x1080 at
60 Hz; interlaced modes are skipped) and scales every size to it. If the TV is switched on after the
board, the picture appears as soon as it is detected. The game runs on virtual terminal 2 so boot
text and the login prompt on terminal 1 never show; for a clean boot add
`extraargs=quiet systemd.show_status=false vt.global_cursor_default=0` to `/boot/armbianEnv.txt`.

## Home Assistant

The firmware talks MQTT through `firmware/mqtt_bridge.py` and announces itself with MQTT discovery:
sensors for state, remaining time and speed; buttons Start, Stop and Reset; switches Disarmed and
TIME_TRAP; numbers Volume and Duration. Under `<prefix>/<room>/`: `command` takes `start`,
`stop` and `reset`; `disarmed/set` ON defuses the bomb (as STOP/DISARM); `trap/set` ON/OFF holds
and releases the TIME TRAP; `volume/set` and `duration/set` take numbers.

The bridge connects to the broker set in config.json; a duration set from Home Assistant goes up to
7200 s.

## Maintenance

- `sudo timer-maintenance on` keeps the timer off (also across reboots) so the HDMI console can be
  used; `sudo timer-maintenance off` brings it back. A file named `MANUTENCAO` on an SD card does the
  same for one boot.
- Esc on a keyboard closes the timer and shows the console (terminal 1); systemd restarts the timer
  after 5 s unless maintenance is on.
- Services: `timer-sdl` (the game), `puzzle-configurator` (web page), `timer-watcher` (applies the
  page's changes), `timer-net-fallback` (network policy). `systemctl status <name>`,
  `journalctl -u <name> -f`; `systemctl restart timer-sdl` reloads config.json.

## Repository

| Path | What it is | On the board |
|---|---|---|
| `firmware/` | `timer-sdl` (C++17: SDL2/KMSDRM, SDL2_ttf, SDL2_mixer, libgpiod, MQTT bridge) | `/usr/lib/timer-nicolau/` |
| `configurator-web/` | Flask web configurator and the root watcher that applies its requests | `/opt/puzzle-configurator/` |
| `configurator-windows/` | Windows app that prepares SD cards | Windows |
| `system-net/`, `packaging/` | network policy, access point, Wi-Fi client, SD import, maintenance; built into `timer-nicolau-system_<version>_all.deb` | `/usr/lib/timer-nicolau/`, systemd units |
| `docs/` | SD card format, hardware reference, investigations and validation records | - |

Both packages are built in containers of the boards' distribution and installed with apt:

```
# system package (architecture-independent)
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/src -w /src debian:trixie bash packaging/build-deb.sh

# firmware (cross-compiled for armhf against the same Debian archive as the boards)
docker build -t timer-nicolau-xbuild:trixie packaging/firmware
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/src -w /src timer-nicolau-xbuild:trixie \
    bash packaging/firmware/build-deb.sh

# on the board
sudo apt install ./timer-nicolau-system_<version>_all.deb ./timer-nicolau-firmware_<version>_armhf.deb
```

## Status and history
- Network design and the failures behind it: [docs/network-design.md](docs/network-design.md).
- Firmware cross-built in a container and shipped as `timer-nicolau-firmware_<version>_armhf.deb`
  (`packaging/firmware/`); it replaces the board-built binary through a systemd drop-in.

## License

[MIT](LICENSE). The bundled DSEG14 font is by keshikan under the SIL Open Font License 1.1
([firmware/fonts/OFL.txt](firmware/fonts/OFL.txt)).
