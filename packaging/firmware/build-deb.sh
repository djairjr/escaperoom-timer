#!/usr/bin/env bash
# Cross-build timer-sdl for armhf and package it as timer-nicolau-firmware_<version>_armhf.deb.
#
# Runs inside the cross-build image (packaging/firmware/Dockerfile):
#   docker build -t timer-nicolau-xbuild:trixie packaging/firmware
#   docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/src -w /src timer-nicolau-xbuild:trixie \
#       bash packaging/firmware/build-deb.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

VERSION=$(tr -d '[:space:]' < firmware/VERSION)
ARCH=armhf
PKG="timer-nicolau-firmware_${VERSION}_${ARCH}"
BUILD=dist/firmware-build
OUT=dist

cmake -S firmware -B "$BUILD" -DCMAKE_TOOLCHAIN_FILE="$PWD/packaging/firmware/armhf-toolchain.cmake" \
      -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD" -j"$(nproc)"

BIN="$BUILD/timer-sdl"
# Read from the binary, never assumed: an armhf label on another architecture's binary would install
# and fail at boot.
file "$BIN" | grep -q 'ARM, EABI5' || { echo "error: $BIN is not an armhf binary" >&2; exit 1; }

STAGE=$(mktemp -d "${TMPDIR:-/tmp}/timer-nicolau-fw.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT

install -Dm755 "$BIN" "$STAGE/usr/lib/timer-nicolau/timer-sdl"
arm-linux-gnueabihf-strip "$STAGE/usr/lib/timer-nicolau/timer-sdl"
install -Dm644 firmware/mqtt_bridge.py "$STAGE/usr/lib/timer-nicolau/mqtt_bridge.py"
install -Dm644 firmware/fonts/DSEG14Classic-Regular.ttf "$STAGE/usr/share/fonts/truetype/DSEG14Classic-Regular.ttf"
install -Dm644 packaging/firmware/20-timer-nicolau-firmware.conf \
    "$STAGE/usr/lib/systemd/system/timer-sdl.service.d/20-timer-nicolau-firmware.conf"
install -Dm644 README.md "$STAGE/usr/share/doc/timer-nicolau-firmware/README.md"
install -Dm644 firmware/fonts/OFL.txt "$STAGE/usr/share/doc/timer-nicolau-firmware/OFL-DSEG14.txt"

mkdir -p "$STAGE/DEBIAN"
cat > "$STAGE/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    systemctl daemon-reload
    systemctl restart timer-sdl.service || true
fi
exit 0
EOF
cat > "$STAGE/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    systemctl daemon-reload || true
    systemctl restart timer-sdl.service || true
fi
exit 0
EOF
chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/postrm"
SIZE=$(du -sk "$STAGE" --exclude=DEBIAN | cut -f1)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: timer-nicolau-firmware
Version: ${VERSION}
Section: games
Priority: optional
Architecture: ${ARCH}
Installed-Size: ${SIZE}
Depends: libsdl2-2.0-0, libsdl2-ttf-2.0-0, libsdl2-mixer-2.0-0, libgpiod3, python3, python3-paho-mqtt
Maintainer: Djair Guilherme da Silva Junior <djair.jr@gmail.com>
Description: Timer-Nicolau escape-room countdown (timer-sdl)
 Full-screen HDMI countdown (SDL2/KMSDRM) driven by four GPIO buttons, with
 sounds, a victory output and Home Assistant control over MQTT. Replaces the
 ExecStart of timer-sdl.service through a drop-in.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/$PKG.deb"
sha256sum "$OUT/$PKG.deb" > "$OUT/$PKG.deb.sha256"
echo "== built =="
ls -la "$OUT/$PKG.deb"
dpkg-deb --contents "$OUT/$PKG.deb"
