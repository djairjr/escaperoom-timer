# Pin configuration reference

How the kernel must configure the Timer-Nicolau pins on an Orange Pi PC Plus (Armbian 26.8
`current`, kernel 6.18), as measured on a board whose buttons work.

## Expected configuration

| Item | Expected |
|---|---|
| `/boot/armbianEnv.txt` | `overlay_prefix=sun8i-h3` and **no `overlays=` / `user_overlays=` line** |
| `/boot/overlay-user` | empty |
| Device tree blob | the default `sun8i-h3-orangepi-pc-plus.dtb` (no `fdtfile=` override) |
| SPI controllers `spi@1c68000`, `spi@1c69000` | **disabled**; no `/dev/spidev*` |
| PC0-PC3 (lines 64-67), PA21 (line 21) pin mux | **MUX UNCLAIMED** (plain GPIO) |
| PC0-PC3 pin config | input, pull-up |
| Line owners | 64-67 input pull-up and 21 output, all `consumer=timer-sdl` |

PC0-PC3 are the SPI0 pins of the 40-pin header (19 MOSI, 21 MISO, 23 SCLK, 24 CS0). Enabling an SPI
overlay (`overlays=spi-spidev`, `param_spidev_spi_bus=0`) would hand them to the SPI controller.

## Checking a board

```
sudo bash scripts/board-hw-snapshot.sh > board.txt     # read-only
```

Compare `board.txt` with the table above, or `diff` the captures of two boards. Between boards the
live device-tree hash always differs (it embeds the board's MAC, serial number and root UUID), as do
the hostname and the level of line 21 (it follows the game state).

## Assembly check

A HAT that is half seated looks fine from above, and nothing in software reports it.

- Every one of the 40 header pins must enter the connector (look along both rows, from the side).
- With the timer running, `journalctl -u timer-sdl -f` must log a state change for each button
  (START -> `State: RUNNING_1x`, A/B -> `PAUSE_INITIAL`, STOP -> `SOLVED`). Do not test with
  `/sys/kernel/debug/gpio`: it misses short presses.
