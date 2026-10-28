# SD card configuration package

**Insert the card with the board powered off, then power it on.** The import runs at boot (12-15 s
after power-on). Inserting a card into a running board has reset it (the logs end
abruptly, no shutdown sequence: a supply dip on the card slot with the 5 V/2 A supply); hot
insertion is supported by the software but not safe on that supply.

The card (FAT32, exFAT or NTFS) holds a folder with these files, at the card root or one folder
below it:

| File | Effect |
|---|---|
| `config.json` | Replaces `/etc/timer-sdl/config.json` as a whole (the previous one is kept as `config.json.bkp.<date>`): every setting comes from the card, e.g. `background_music_enabled: false` turns the music off. Must be valid JSON with `timer_duration_sec`. |
| `sfx/*.mp3`, `*.wav`, `*.ogg`, `*.flac` | Copied to `/var/lib/timer-nicolau/sfx/`. |
| `wifi.json` | `{"ssid": "Network", "password": "secret"}` - the board joins that Wi-Fi network (on `wlan1`) and keeps it across reboots. Empty password = open network. |

After applying, the timer restarts and the board writes `TIMER-NICOLAU-RESULTADO.txt` next to the
files, listing what was applied or what failed. A package is applied once per content (its hash is
kept in `.timer-nicolau-applied`), so the card can stay in the slot.

The `.timer-nicolau-config` marker written by the Windows configurator is accepted but no longer
required.

## Maintenance mode

A file named `MANUTENCAO` (any case, any extension, e.g. `manutencao.txt`) at the card root keeps
the timer off for that boot, leaving the HDMI console usable. Remove the card and reboot to return
to normal. From a shell: `sudo timer-maintenance on` (persists across reboots) and
`sudo timer-maintenance off`.

## Configuration access point

The access point `Nicolau-XXXX` is the way to configure the board from a phone. It is up whenever the
board is not on a Wi-Fi network: at once when the cable is plugged in at boot (the cable does not
replace it), and after 20 s without a cable if the saved Wi-Fi did not connect. The password is the
web configurator login (default `timersdl1234!`). Join it and open `http://192.168.4.1`; any address
also lands there. Joining a Wi-Fi network from the web page turns the access point off once the board
gets an address on it.
