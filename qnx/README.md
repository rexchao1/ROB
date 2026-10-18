# The referee on the QNX Pi

The rules and the game state run on the Pi (QNX 8.0, Python 3.14, standard library only): `python3 -m brain.referee` plays every game through the Table that the brain on the Mac serves (`brain/remote.py`). The Mac keeps the robot, the camera, the voice, the ears and the clock. The Pi needs nothing but Python 3 and tar.

    qnx/deploy.sh                                   # copy the referee to ~/gm on the Pi and check it starts
    npm run brain -- --referee remote --pitch 25    # on the Mac: the Table on :8090, no loop of its own
    qnx/referee.sh http://172.20.10.13:8090         # the referee on the Pi, in the foreground (Ctrl-C stops it)

Both scripts take the Pi as `user@host` (default `$GM_PI`, else `qnxuser@10.77.0.1` when the Mac is on the Pi's own network, else `qnxuser@172.20.10.14` on the phone hotspot) and extra ssh options in `$GM_SSH_OPTS`. With `--table-token T` on the brain, set `GM_TABLE_TOKEN=T` before `qnx/referee.sh`.

The referee can start before or after the brain and survives either restarting: it keeps trying to reach the Table, attaches again after a restart, and a game cut off that way ends with the recovery line. One referee at a time: a new one takes the table and the old one stops.

In test mode (`--test --referee remote`) the brain's virtual clock waits for an attached referee between its calls, so a game played from the Pi tells the fake gateway exactly what the brain alone would (`test/integration/referee.test.ts` runs the referee as a separate process over loopback).

## The Pi's own network

The Pi hosts the game's Wi-Fi network itself and stays on QNX; the robot, the Mac and the Pi all join it. `qnx/ap/net.conf` holds the numbers: `gamemaster`, 2.4 GHz channel 6, WPA2 (CCMP), the Pi at 10.77.0.1, the Mac at 10.77.0.2 (set by hand: its Wi-Fi uses a private MAC per network), the robot and anything else from 10.77.0.100-199. No router and no DNS are handed out, so the Mac keeps its internet on the iPhone's USB link. The subnet is not the hotspot's 172.20.10.0/28: the iPhone gives the Mac that same subnet over USB, and the same subnet on two interfaces would send the Pi's traffic to the phone. The password is `GM_WIFI_PASSWORD` in `.env.local` (gitignored; `qnx/ap.sh install` makes one if it is missing).

How QNX does it: the image has no hostapd and no DHCP server, but its wpa_supplicant 2.11 is built with AP support and the Wi-Fi driver (QWDI, Cypress DHD over SDIO) reports it (`DRIVER_FLAGS`: `AP`; `GET_CAPABILITY modes`: `AP`; `key_mgmt` `WPA-PSK`; `pairwise` `CCMP`). So the access point is a `mode=2` network for the same wpa_supplicant that `start_net.sh` starts at boot on bcm0, and `qnx/ap/dhcpd.py` (standard library, root for port 67) is the DHCP server. It answers only requests that arrive on bcm0, so an Ethernet cable into another network never hears from it.

    qnx/ap.sh install            # copy qnx/ap and the access point's setup to ~/gmnet on the Pi; nothing else changes
    qnx/ap.sh trial [SECONDS] [bcm1]   # the access point now, by hand; back to the hotspot by itself after SECONDS (300)
    qnx/ap.sh persist            # back up the two boot files, then make the access point the boot setup, on probation
    qnx/ap.sh reboot
    qnx/ap.sh confirm            # from the new network: keep it (a trial: keep it until reboot)
    qnx/ap.sh revert             # back to the hotspot: end a trial, or put the backups back and reboot
    qnx/ap.sh status             # the boot setup, the access point and its clients, dhcpd, the leases, the referee
    qnx/ap.sh referee-restart    # after qnx/deploy.sh

On the Pi, `~/gmnet/gm-net.sh` does the work (as root). `persist` changes two files, each backed up to `~/gmnet/backup/` first: `/data/var/etc/settings/wpa_supplicant.conf` becomes the access point's setup, and `/system/etc/startup/post_startup.sh` gets one line before its last `exit 0` that runs `gm-net.sh boot` in the background. At boot that stops dhcpcd on bcm0, gives bcm0 its fixed address, starts dhcpd and starts the referee as qnxuser from `~/gm` against `http://10.77.0.2:8090`, again whenever it stops, except when another referee took the table (`qnx/referee.sh`; `referee-restart` brings it back). Logs are in `~/gmnet/log/`.

Nothing stays without proof. A trial writes no file: it runs the access point by hand and goes back to the hotspot by itself after its time unless confirmed (if bcm0 then gets no hotspot address in 90 s, the Pi reboots, which also gives the hotspot setup back). A persisted setup is on probation: each boot that is not confirmed within 15 minutes puts the backed-up files back and reboots onto the hotspot. Last resort, with the SD card in the Mac: touch `wpa_supplicant.conf` on its boot partition (the hotspot setup is kept there, and `copy_settings.sh` copies it over the access point's setup at boot when it is newer). `gm-net.sh boot` then finds no access point and does nothing, and `qnx/ap.sh revert` from the hotspot takes the boot line out.

### The changeover

Once, from the phone hotspot to the Pi's network. The Mac's Wi-Fi changes in steps 4 and 5 only.

1. Power: the Pi on its 27 W USB-C supply.
2. Still on the hotspot: `qnx/ap.sh install`. To prove it first: `qnx/ap.sh trial 300 bcm1` runs the access point beside the hotspot link on the hotspot's channel, so the Mac keeps its ssh session. Join `gamemaster` from a phone; `qnx/ap.sh status` should list the phone and its 10.77.0.1xx lease. If the driver will not run a second interface, `qnx/ap.sh trial 300` runs it on bcm0 instead: the Pi leaves the hotspot for those 5 minutes and comes back by itself.
3. The Mac's internet over USB: plug the iPhone into the Mac with Personal Hotspot on; System Settings, Network shows iPhone USB connected. In System Settings, Wi-Fi, turn Auto-Join off for the iPhone's network, so the Mac does not leave `gamemaster` (no internet) for it.
4. The Pi: `qnx/ap.sh persist`, then `qnx/ap.sh reboot`. A minute later `gamemaster` is up, with 15 minutes to be confirmed.
5. The Mac: `scripts/wifi.sh game`, then `qnx/ap.sh confirm`.
6. The robot: its setup page (README, "Setting up the robot"): Wi-Fi `gamemaster` and the password, OTA `http://10.77.0.2:8768/ota/`, gateway `ws://10.77.0.2:8765/`. From the Mac that means `scripts/wifi.sh back`, the robot's "Xiaozhi..." network, then `scripts/wifi.sh game` again.
7. The gateway: restart it with `VISION_HOST=10.77.0.2` (`scripts/game.sh` starts it so, and refuses one running with the old address). Then README, "Running a game".
