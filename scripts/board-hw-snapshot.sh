#!/bin/bash
# board-hw-snapshot.sh - record how this board's kernel configures the Timer-Nicolau pins.
#
# Read-only. Run as root on a board; prints a stable, diff-friendly report covering everything that
# decides whether the button lines reach timer-sdl: boot config and overlays, device tree, pin mux,
# GPIO ownership and levels. Compare two boards with:  diff board-a.txt board-b.txt
set -u
PINS="21 64 65 66 67"   # PA21 output; PC0-PC3 START, A, B, STOP/DISARM

section() { printf '\n===== %s\n' "$1"; }

mount | grep -q ' /sys/kernel/debug ' || mount -t debugfs none /sys/kernel/debug 2>/dev/null

section "identity"
echo "hostname: $(hostname)"
echo "model: $(tr -d '\0' < /proc/device-tree/model)"
echo "compatible: $(tr '\0' ' ' < /proc/device-tree/compatible)"
echo "kernel: $(uname -r)"
grep -E '^(BOARD|VERSION|LINUXFAMILY|BRANCH)=' /etc/armbian-release 2>/dev/null

section "/proc/cmdline (root UUID masked)"
sed -E 's/root=UUID=[0-9a-f-]+/root=UUID=<masked>/' /proc/cmdline

section "/boot/armbianEnv.txt (rootdev masked)"
sed -E 's/^rootdev=.*/rootdev=<masked>/' /boot/armbianEnv.txt

section "device tree blob and boot script (sha256)"
grep -E '^fdtfile=' /boot/armbianEnv.txt || echo "fdtfile: (default)"
echo "/boot/dtb -> $(readlink /boot/dtb)"
sha256sum /boot/dtb/sun8i-h3-orangepi-pc-plus.dtb /boot/boot.scr 2>/dev/null | sed 's|  | |'
# What the kernel actually booted with, independent of the files on disk.
echo "live device tree: $(cat /sys/firmware/fdt 2>/dev/null | sha256sum | cut -c1-64)"

section "user overlays (/boot/overlay-user)"
ls -la /boot/overlay-user 2>/dev/null || echo "(none)"

section "peripherals that can claim PC0-PC3 / PA21 (device-tree status)"
for n in /proc/device-tree/soc/spi@* /proc/device-tree/soc/mmc@* /proc/device-tree/soc/serial@* \
         /proc/device-tree/soc/i2c@* /proc/device-tree/soc/pwm@*; do
    [ -d "$n" ] || continue
    printf '%-42s %s\n' "${n#/proc/device-tree/soc/}" "$(tr -d '\0' < "$n/status" 2>/dev/null || echo okay)"
done
ls /dev/spidev* 2>/dev/null || echo "/dev/spidev*: none"

section "pin mux (pinctrl 1c20800)"
for p in $PINS; do
    grep -E "^pin $p " /sys/kernel/debug/pinctrl/1c20800.pinctrl/pinmux-pins
done

section "pin config (bias/drive)"
for p in $PINS; do
    grep -E "^pin $p " /sys/kernel/debug/pinctrl/1c20800.pinctrl/pinconf-pins 2>/dev/null
done

section "GPIO line ownership (gpiochip0)"
for p in $PINS; do
    gpioinfo -c gpiochip0 2>/dev/null | grep -E "^\s+line\s+$p:"
done

section "GPIO levels now (buttons released; line 21 follows the game: high after a victory)"
grep -E "gpio-($(echo $PINS | tr ' ' '|')) " /sys/kernel/debug/gpio

section "relevant modules"
lsmod | awk 'NR == 1 || /spi|gpio|sun8i|sunxi/ {print $1}' | sort

section "timer-sdl"
systemctl show -p ExecStart timer-sdl | grep -o 'path=[^ ]*'
dpkg-query -W -f='${Package} ${Version}\n' timer-nicolau-system timer-nicolau-firmware 2>/dev/null
