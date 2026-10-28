#!/usr/bin/env bash
# Build timer-nicolau-system_<version>_all.deb: network fallback (access point), Wi-Fi client,
# SD-card import and the web configurator with its watcher.
#
# Run inside the board's distribution so dpkg-deb matches it:
#   docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/src -w /src debian:trixie bash packaging/build-deb.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VERSION=$(tr -d '[:space:]' < VERSION)
PKG="timer-nicolau-system_${VERSION}_all"
OUT=dist

for f in system-net/lib/* packaging/postinst packaging/prerm configurator-web/scripts/timer-watcher.sh; do
    bash -n "$f"
done

STAGE=$(mktemp -d "${TMPDIR:-/tmp}/timer-nicolau-deb.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT

install -Dm644 system-net/lib/common.sh "$STAGE/usr/lib/timer-nicolau/common.sh"
for t in timer-ap timer-net-fallback timer-wifi-connect timer-wifi-scan timer-sd-import; do
    install -Dm755 "system-net/lib/$t" "$STAGE/usr/lib/timer-nicolau/$t"
done
for u in system-net/units/*.service; do
    install -Dm644 "$u" "$STAGE/usr/lib/systemd/system/$(basename "$u")"
done
install -Dm644 configurator-web/puzzle-configurator.service "$STAGE/usr/lib/systemd/system/puzzle-configurator.service"
# Drop-in for the timer-sdl unit that lives in /etc/systemd/system (written at install time).
install -Dm644 system-net/units/timer-sdl.service.d/10-timer-nicolau-maintenance.conf \
    "$STAGE/usr/lib/systemd/system/timer-sdl.service.d/10-timer-nicolau-maintenance.conf"
install -Dm755 system-net/lib/timer-maintenance "$STAGE/usr/sbin/timer-maintenance"
install -Dm644 system-net/network/30-timer-wifi-client.network \
    "$STAGE/usr/lib/systemd/network/30-timer-wifi-client.network"
install -Dm644 system-net/udev/99-timer-nicolau-sd.rules "$STAGE/usr/lib/udev/rules.d/99-timer-nicolau-sd.rules"
install -Dm644 system-net/sysctl/60-timer-nicolau-arp.conf "$STAGE/usr/lib/sysctl.d/60-timer-nicolau-arp.conf"
install -Dm644 system-net/net.conf "$STAGE/etc/timer-nicolau/net.conf"

# Web configurator code. setup.json is per board (it holds the login password) and stays as it is.
WEB="$STAGE/opt/puzzle-configurator"
install -Dm755 configurator-web/server.py "$WEB/server.py"
install -Dm755 configurator-web/scripts/timer-watcher.sh "$WEB/scripts/timer-watcher.sh"
for f in configurator-web/puzzle_configurator/*.py; do
    install -Dm644 "$f" "$WEB/puzzle_configurator/$(basename "$f")"
done
for f in configurator-web/puzzle_configurator/locales/*.json; do
    install -Dm644 "$f" "$WEB/puzzle_configurator/locales/$(basename "$f")"
done
for f in configurator-web/static/*; do
    install -Dm644 "$f" "$WEB/static/$(basename "$f")"
done

DOC="$STAGE/usr/share/doc/timer-nicolau-system"
install -Dm644 README.md "$DOC/README.md"
install -Dm644 docs/network-design.md "$DOC/network-design.md"
install -Dm644 docs/sd-card-package.md "$DOC/sd-card-package.md"

mkdir -p "$STAGE/DEBIAN"
install -m755 packaging/postinst packaging/prerm "$STAGE/DEBIAN/"
echo /etc/timer-nicolau/net.conf > "$STAGE/DEBIAN/conffiles"
SIZE=$(du -sk "$STAGE" --exclude=DEBIAN | cut -f1)
cat > "$STAGE/DEBIAN/control" <<EOF
Package: timer-nicolau-system
Version: ${VERSION}
Section: misc
Priority: optional
Architecture: all
Installed-Size: ${SIZE}
Depends: passwd, hostapd, dnsmasq-base, wpasupplicant, iw, iproute2, python3, python3-flask, systemd
Maintainer: Djair Guilherme da Silva Junior <djair.jr@gmail.com>
Description: Timer-Nicolau network fallback, Wi-Fi client, SD import and web configurator
 Brings up a configuration access point (hostapd + dnsmasq bound to the AP
 interface) when the board finds no network at boot, joins Wi-Fi networks through
 systemd-networkd, applies configuration packages from an SD card, and ships the
 web configurator with the root watcher that applies its requests.
EOF

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT/$PKG.deb"
sha256sum "$OUT/$PKG.deb" > "$OUT/$PKG.deb.sha256"
echo "== built =="
ls -la "$OUT/$PKG.deb"
dpkg-deb --contents "$OUT/$PKG.deb"
