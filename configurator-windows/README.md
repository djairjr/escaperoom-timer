# Timer-Nicolau Configurator (Windows)

A Windows app that prepares an SD card with a Timer-Nicolau configuration: `config.json`, sound
files and, optionally, the Wi-Fi network the board should join. The board applies the card at
boot. The app's interface is in Brazilian Portuguese (the product's users); labels below are quoted
as they appear on screen.

## Installing

Run `Timer-Nicolau-Configurator-Setup.exe` and follow the installer; tick "Executar Timer-Nicolau
Configurator" at the end. A standalone `Timer-Nicolau-Configurator.exe` also runs without
installation.

Building from source (on Windows): `pip install -r requirements.txt`, then
`pyinstaller Timer-Nicolau-Configurator.spec` for the .exe and Inno Setup with `installer.iss` for
the installer.

## Tabs

### Geral

| Field | Meaning |
|---|---|
| "Nome da Sala" | room name shown on screen and used in Home Assistant (spaces become `_` there) |
| "Duração (s)" | game length, 60-7200 s (3600 = 60 min) |
| "Pausa do 1º botão (s)" | freeze after the first of the two robbery buttons is pressed, 0-10 s |
| "Multiplicador Acel." | countdown speed during the robbery, 1x-5x |
| "Timeout Vitória (s)" | how long the victory / game-over screen stays before returning to ready |

### Display

| Field | Meaning |
|---|---|
| "Mensagem IDLE" | text on the ready screen (e.g. `AMBIENTE\nSEGURO`) |
| "Mensagem Vitória" | text when the players defuse the bomb |
| "Mensagem Game Over" | text when time runs out |
| "Brilho (%)" | screen brightness, 0-100 |

`\n` breaks a line on screen: `ACESSO\nLIBERADO` shows ACESSO above LIBERADO.

### Áudio

| Field | Meaning |
|---|---|
| "Volume" | overall volume, 0-128 |
| "Sons Ativados" | all sounds on/off |
| "Sons Customizados" | use the sound files chosen below |
| "Música de Fundo" | background music on the ready screen |

For each sound (tick, alarm, victory, ...) press "..." and pick a file. Sounds left empty keep the
board's default.

### Wi-Fi

| Field | Meaning |
|---|---|
| "Rede Wi-Fi (SSID)" | network the board joins; leave empty to keep the board's current Wi-Fi |
| "Senha do Wi-Fi" | its password (8-63 characters; empty for an open network) |

With the network cable plugged in the board uses the cable; the Wi-Fi network is saved and used
when the cable is unplugged.

### MQTT

| Field | Meaning |
|---|---|
| "Broker" | MQTT server address; empty = no Home Assistant |
| "Porta" | port, usually 1883 |
| "Usuário" / "Senha" | MQTT credentials, if the broker requires them |
| "Prefixo Tópico" | topic prefix (default `nicolau/timer/`) |
| "HA Discovery Prefix" | Home Assistant discovery prefix (default `homeassistant`) |

### GPIO

| Field | Meaning |
|---|---|
| "Pino Desarme (line)" | GPIO line of the victory output; 21 (PA21, header pin 26) on the standard wiring |
| "Active High" | output polarity |

### Avançado

"Log Verbosity": amount of detail in the board's logs, 0-3; keep 1.

## Exporting to an SD card

1. Insert an SD card (FAT32 or exFAT) in the computer.
2. Press "Generate & Export" and choose the card (or a folder on it).
3. The app writes `config.json`, `sfx/`, `wifi.json` (only when a network was entered), the
   `.timer-nicolau-config` marker and a `README.txt` with these instructions.

## Applying on the board

1. **Switch the board off**, insert the card, switch it on. Inserting a card into a running board
   can reset it.
2. About 15 s after power-on the configuration is applied and the timer restarts.
3. The outcome is written to the card as `TIMER-NICOLAU-RESULTADO.txt`; open it on the computer.
   The card can stay in the board: the same content is not applied twice.

`config.json` replaces the whole configuration (the previous one is kept on the board as a backup).
Details: [../docs/sd-card-package.md](../docs/sd-card-package.md).

## Troubleshooting

- **Nothing changed on the board** - read `TIMER-NICOLAU-RESULTADO.txt` on the card: it lists what
  was applied or why it was rejected. No such file means the card was not read: check that it is
  FAT32/exFAT and that `config.json` is at the root or one folder below.
- **Export refused** - the message lists the field out of range.
- **Room missing in Home Assistant** - the broker must be filled in; a room name with spaces appears
  with `_`; removing the old device in Home Assistant and waiting a few seconds may be needed.
- **No sound** - "Volume" above 0, "Sons Ativados" ticked, and a file format the board plays
  (mp3, wav, ogg, flac).
- **Board unreachable on the network** - the board opens its own network
  `Nicolau-XXXX` within seconds (with the cable) or after 20 s (without it, if no Wi-Fi connects); join it and open `http://192.168.4.1`.
