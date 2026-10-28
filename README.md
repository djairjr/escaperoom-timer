# Escape Room Countdown Timer - Wifi Configurable

A bomb-style countdown timer for escape rooms. It shows a big countdown on a TV, plays sounds, reads
the buttons wired into the room and closes a relay (door lock, siren, lights) when the players win.
The game master runs it from the room buttons or from a phone browser.

**It is designed to work with any HDMI TV.** Plug the board into the TV's HDMI input and that is all:
the picture uses the best resolution the TV offers (up to 1920x1080) and **the sound comes out of
the TV's own speakers through the same HDMI cable** - no amplifier or speakers to buy. Set the volume
with the TV's remote (and `sound_volume` in the settings). It runs on an **Orange Pi PC Plus**
(Armbian, Debian 13 trixie, armhf).

This first part is for **game masters**. Installers and developers: skip to
[Wiring](#wiring) and below.

## How the timer works

The players see a large seven-segment countdown (60:00 by default) whose colour changes as time runs
out: green above 50% of the time left, then yellow, orange and a flashing red in the last 10%.

1. **Ready.** The screen shows the room name and the idle message ("AMBIENTE SEGURO"); background
   music plays. The game master presses **Play** (or the green button) to start.
2. **Counting at 1x.** One second of countdown per real second, with a tick each second.
3. **The first of the two player buttons pressed starts the robbery ("ROUBO").** The display freezes
   for 3 seconds with an alarm, then the countdown runs at **2x** (red "2x" on screen). The other
   player button becomes the **TIME TRAP**.
4. **TIME TRAP.** While a player *holds* the trap button the countdown slows back to **1x** (green
   "1x" on screen). Releasing it returns to 2x. It is the only way to slow the bomb down.
5. **Win: STOP / DISARM.** Pressed at any time during the game, it stops the countdown, shows the
   victory message ("ACESSO LIBERADO") in yellow, plays the victory sound and drives the output
   **high** (relay, magnetic lock, siren, lights).
6. **Lose: time runs out.** The screen shows the game-over message ("BOMBA EXPLODIU") and the
   explosion sound plays; the output stays low.
7. **Back to ready.** After the victory or game-over sound ends, Play (or the green button) returns
   to the ready screen; otherwise it returns by itself after `victory_timeout_sec`.

## The buttons

Four buttons are wired to the board in the room:

| Button | Wire | Who presses it | What it does |
|---|---|---|---|
| START / Play | green | game master | starts the countdown; after a game, returns to the ready screen |
| A | yellow | players | one of two identical buttons in the room |
| B | blue | players | the other identical button |
| STOP / DISARM | red | players (hidden in the room) | defuses the bomb: the players win |

**A and B look the same, but the first one pressed decides their roles** (robbery and TIME TRAP).
That is the trick of the room.

## Remote control from your phone or computer

The game master can run the game from a browser, with the same effect as the room buttons. Open the
**Game** tab of the web page (**Jogo** in Portuguese) (see [Connecting](#connecting-to-the-board) below):

| Control | Same as | What it does |
|---|---|---|
| **Play** | green button | starts the game; after a win or a loss, returns to the ready screen |
| **Acceleration** switch (*Aceleração*) | yellow and blue buttons | from 1x, switching it **on** starts the robbery (3 s freeze, then 2x). While running, **on** = 2x and **off** = TIME TRAP (1x); flip it again to return to 2x |
| **Stop** | red button | asks for confirmation, then ends the game as a win ("ACESSO LIBERADO", output high) |
| **Reset** | - | asks for confirmation and puts the timer back in its initial condition from any state (ready screen, full time, output low), cutting any sound that is playing |

The page also shows the state and the time left. Controls that make no sense at the moment are greyed
out (for example Play during a game). The room buttons keep working at the same time.

## Connecting to the board

> **The board's own Wi-Fi network is the way to connect and configure it.** It is on whenever the
> board is not connected to a Wi-Fi network - **including when the Ethernet cable is plugged in** - so
> a phone is all you need; no router or network at the site.

1. Power the board. The Wi-Fi network `Nicolau-XXXX` (XXXX = last digits of its Wi-Fi address)
   appears within seconds with the cable plugged in, or about 20 s after power-on without it.
2. Join it from the phone. The password is the web page's (default `timersdl1234!`).
3. Open `http://192.168.4.1` (any address leads there) and log in with the same password.

On a venue network you can also open `http://<board address>/` from any computer or phone on it.
Choosing the venue's Wi-Fi network in the page makes the board join it and turn its own network off.
To change the password, edit `http_password` in `/opt/puzzle-configurator/setup.json` (the board's
Wi-Fi password follows it), then restart `puzzle-configurator` and `timer-ap` or reboot the board.

The board's network and the web page never interfere with the game: they run in separate services
and the timer does not wait for them. The timer works the same with or without any network.

## Configuring the game

Everything is edited in the web page (tabs **Game**, **Settings**, **Sounds**, **Wi-Fi / HA**, **Status**).
The page speaks the **language of the board's Linux locale** (Brazilian Portuguese and English are
included), with no setting in the page. Change it the usual way on the board, as root:
`sudo update-locale LANG=pt_BR.UTF-8 LANGUAGE=pt_BR:en LC_MESSAGES=pt_BR.UTF-8` (or
`sudo dpkg-reconfigure locales`); the page follows on the next load, no restart. Set `LANGUAGE` and
`LC_MESSAGES` too: by the POSIX rules they win over `LANG` for messages.
A language without a catalog shows in English.
Translations are standard gettext `.po` files, plain text you edit with any editor or Poedit:
`/usr/share/timer-nicolau/locale/<locale>/LC_MESSAGES/timer-nicolau.po`. Put your own copy in
`/etc/timer-nicolau/locale/<locale>/LC_MESSAGES/timer-nicolau.po` (it wins and survives upgrades); to add a
language copy `timer-nicolau.pot` there, translate the `msgstr` lines and set `X-Native-Name`.
In the source tree `scripts/gettext-update.py` keeps the catalogs in step with the code.
You can edit:
game length, robbery speed, freeze time, screen texts, volume, sounds (upload your own), Wi-Fi and
Home Assistant. **Save settings** (*Salvar configuração*) applies it and restarts the timer. The most useful settings:

| Setting | Meaning |
|---|---|
| `timer_duration_sec` | length of a game (3600 = 60 min) |
| `accel_multiplier` | robbery speed, 1-10 (default 2) |
| `trap_pause_seconds` | freeze after the first player button, 0-30 s (default 3) |
| `room_name`, `idle_message`, `victory_message`, `game_over_message` | screen texts: type `\n` (or press Enter) to start a new line on the TV; without it a long text wraps by itself and shrinks to fit |
| `victory_timeout_sec` | seconds on the victory or game-over screen before returning to ready |
| `sound_volume` (0-128), `sounds_enabled`, `background_music_enabled`, `sound_files.*` | sound; the TV's own volume still applies |

The full list and the other ways to configure (SD card, Home Assistant) are under
[Configuration reference](#configuration-reference).

---

# For installers and developers

Internally the game is one state machine in `firmware/src/main.cpp`:
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

## Configuration reference

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

The game has no time penalty by design; a `penalty_seconds` left in an older `config.json` is ignored and hidden from the web page.

There are three ways to change the configuration, all of which end in the same file:

- **Web configurator** - through the board's own Wi-Fi network (see
  [Connecting](#connecting-to-the-board), the main way) or `http://<board>/` on the local network.
  Password protected. Also uploads sounds and joins Wi-Fi networks.
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
  Wi-Fi. See [Connecting](#connecting-to-the-board).

The timer runs the same with or without any network.

## Display and sound

Any HDMI TV works. On start the firmware picks the best progressive mode the TV reports (largest, up
to 1920x1080 at 60 Hz; interlaced modes are skipped) and scales every size to it. If the TV is
switched on after the board, the picture appears as soon as it is detected. Audio goes out over HDMI
(ALSA `hw:1,0`, the board's HDMI sound card), so the TV's speakers play it; the 3.5 mm jack is not
used.

For a clean boot the game runs on virtual terminal 2, so the login prompt on terminal 1 never shows;
add `extraargs=quiet systemd.show_status=false vt.global_cursor_default=0` to `/boot/armbianEnv.txt`
to hide the boot text as well.

## Remote control internals

The web page sends one word (`play`, `accel`, `stop` or `reset`) to a local UNIX socket
(`/run/timer-nicolau/control.sock`), read without blocking in the main loop of `timer-sdl`, and reads a
snapshot (`/run/timer-nicolau/game.json`, rewritten twice a second). Neither side ever waits for the
other, and the game does not depend on the web or the network. The events are the ones the state
machine already has for the buttons and MQTT (`start`, `stop`, `trap_on`, `trap_off`, `reset`).

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

The code is under the [MIT license](LICENSE). The bundled DSEG14 font is by keshikan under the SIL
Open Font License 1.1 ([firmware/fonts/OFL.txt](firmware/fonts/OFL.txt)).

**The name and logo of Nicolau dos Brinquedos** (`configurator-web/static/logoNicolaudosBrinquedos.svg`,
`configurator-windows/icone.ico` and the matching texts of the web configurator) are the author's
brand and are **not** covered by the MIT license: replace them in your own builds.
