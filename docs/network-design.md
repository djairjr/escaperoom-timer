# Network design notes

Why the network side of timer-nicolau-system is built the way it is. Each rule below comes from a
failure that was reproduced on an Orange Pi PC Plus (Armbian trixie, systemd 257).

## One DHCP client: systemd-networkd

Never run a second DHCP client (dhcpcd, dhclient) next to systemd-networkd, not even for Wi-Fi.
networkd's DHCPv6 client binds UDP 546; when another process holds that port first, networkd logs

```
end0: Could not acquire DHCPv6 lease on NDisc request: Address already in use
end0: Failed
```

and loops reconfiguring the interface, during which the default and prefix routes disappear: the
board keeps an address but is unreachable. A client started by hand survives `apt purge` until the
next reboot. Check with `ss -ulpn | grep ':546 '`: only `systemd-network` may appear. The Wi-Fi
client (wlan1) therefore gets its address from networkd as well (`30-timer-wifi-client.network`).

## dnsmasq for the access point, bound to the AP interface

dnsmasq is a DHCP *server* and does not touch port 546. Its usual failure on these systems is the
wildcard bind on port 53 colliding with systemd-resolved's stub (`failed to create listening
socket for port 53`). timer-ap runs it with `interface=wlan0`, `bind-interfaces` and
`listen-address=192.168.4.1`, without `dnsmasq.service`, so the two coexist.

## The access point stays with the cable

The access point is the way to configure the board from a phone, and a phone is not on the cable's
network. timer-net-fallback therefore raises it at boot as soon as the cable has carrier, and only a
Wi-Fi client that is associated and holds an address for 30 s turns it off. A default route no longer
counts as "network present". Without a cable it waits `BOOT_WAIT` (20 s) for the saved Wi-Fi.

## Cable wins over Wi-Fi

With end0 and wlan1 on the same subnet the kernel answers ARP for both addresses on both interfaces
("ARP flux"); a consumer router learned the board through the wrong MAC and lost it until the
router rebooted. timer-net-fallback keeps the Wi-Fi client down while the cable has carrier, and
60-timer-nicolau-arp.conf (`arp_ignore=1`, `arp_announce=2`) covers the seconds of a password check.

## One radio, two interfaces

wlan0 (access point) and wlan1 (client) share the rtl8189fs radio. A scan on wlan1 leaves the AP
channel and drops the phones joined to it, so timer-ap scans once before raising the AP and the web
configurator's network list comes from that scan while the AP is up. Joining a network stops the
AP first and restores it if the join fails.
