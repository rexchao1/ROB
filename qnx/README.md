# The referee on the QNX Pi

The rules and the game state run on the Pi (QNX 8.0, Python 3.14, standard library only): `python3 -m brain.referee` plays every game through the Table that the brain on the Mac serves (`brain/remote.py`). The Mac keeps the robot, the camera, the voice, the ears and the clock. The Pi needs nothing but Python 3 and tar.

    qnx/deploy.sh                                   # copy the referee to ~/gm on the Pi and check it starts
    npm run brain -- --referee remote --pitch 25    # on the Mac: the Table on :8090, no loop of its own
    qnx/referee.sh http://172.20.10.13:8090         # the referee on the Pi, in the foreground (Ctrl-C stops it)

Both scripts take the Pi as `user@host` (default `$GM_PI`, else `qnxuser@10.77.0.1` when the Mac is on the Pi's own network, else `qnxuser@172.20.10.14` on the phone hotspot) and extra ssh options in `$GM_SSH_OPTS`. With `--table-token T` on the brain, set `GM_TABLE_TOKEN=T` before `qnx/referee.sh`.

The referee can start before or after the brain and survives either restarting: it keeps trying to reach the Table, attaches again after a restart, and a game cut off that way ends with the recovery line. One referee at a time: a new one takes the table and the old one stops.

In test mode (`--test --referee remote`) the brain's virtual clock waits for an attached referee between its calls, so a game played from the Pi tells the fake gateway exactly what the brain alone would (`test/integration/referee.test.ts` runs the referee as a separate process over loopback).

## Facts and talk on the Pi

The Pi runs the lobby, welcome and every game's rules. It also calls the talk model
when it has internet and a key. It reads the Mac's provider, model, effort and
personality before each reply. When talk is off, the key is missing or a call fails,
it asks the Mac's Table instead. A failed Pi call pauses local attempts for a minute.
Hearing, voice, camera and the robot connection stay on the Mac.

Say "ROB, remember that we hate Wordle", "forget that" for the last selected fact,
"forget everything" for facts and game totals, or "what do you remember?" in the
welcome. ROB keeps at most 30 entries, each at most 100 characters. Each game's play
count and public side-win totals take one entry; a full store rejects new entries.
Seats, named winners and private assignments never enter those totals.

Facts live in `~/gm-memory/facts.json`, outside `~/gm`, which deploy replaces.
`--facts-file PATH` or `GM_FACTS_FILE` changes that path. Writes are atomic and happen
only when facts or totals change. Without the Pi, facts stay in RAM for that Mac
session. Recent dialogue is RAM only, bounded to 12 lines, kept through naps and
cleared on greeting/reset, game end and lobby teardown; process exit drops it too.
Game end clears dialogue so the next lobby cannot inherit the previous conversation.
ROB keeps no transcripts, turn summaries or private roles on disk and does not
recognize people across sessions. Only selected group facts and public game totals
are durable memory.

To give the Pi the Anthropic key deliberately, run on the Mac:

    qnx/deploy.sh --with-key

This deploys the code and copies only `ANTHROPIC_API_KEY` and, when present,
`ANTHROPIC_WORKSPACE_ID` from the Mac's `.env.local` to `~/gm-memory/talk.env`, mode
600. Values are never printed. Normal deploys neither copy nor remove keys. The
referee reads that file at startup; `--key-file PATH` or `GM_PI_KEY_FILE` changes its
location. No settings file is written on the Pi. After deployment, restart the
referee with `qnx/ap.sh referee-restart` to load the new code and key.

## The Pi's own network

The Pi hosts the game's Wi-Fi network itself and stays on QNX; the robot, the Mac and the Pi all join it. `qnx/ap/net.conf` holds the numbers: `gamemaster`, 2.4 GHz channel 6, WPA2 (CCMP), the Pi at 10.77.0.1, the Mac at 10.77.0.2 (set by hand: its Wi-Fi uses a private MAC per network), the robot and anything else from 10.77.0.100-199. No router and no DNS are handed out, so the Mac keeps its internet on the iPhone's USB link. The subnet is not the hotspot's 172.20.10.0/28: the iPhone gives the Mac that same subnet over USB, and the same subnet on two interfaces would send the Pi's traffic to the phone. The password is `GM_WIFI_PASSWORD` in `.env.local` (gitignored; `qnx/ap.sh install` makes one if it is missing).

How QNX does it: the image has no hostapd and no DHCP server, but its wpa_supplicant 2.11 is built with AP support and the Wi-Fi driver (QWDI, Cypress DHD over SDIO) reports it (`DRIVER_FLAGS`: `AP`; `GET_CAPABILITY modes`: `AP`; `key_mgmt` `WPA-PSK`; `pairwise` `CCMP`). So the access point is a `mode=2` network for the same wpa_supplicant that `start_net.sh` starts at boot on bcm0, and `qnx/ap/dhcpd.py` (standard library, root for port 67) is the DHCP server. It answers only requests that arrive on the access point's interface (bcm0, or bcm1 with the uplink below), so the hotspot or an Ethernet cable into another network never hears from it.

    qnx/ap.sh install            # copy qnx/ap and the access point's setup to ~/gmnet on the Pi; nothing else changes
    qnx/ap.sh trial [SECONDS] [bcm1]   # the access point now, by hand; back to the hotspot by itself after SECONDS (300)
    qnx/ap.sh persist            # back up the two boot files, then make the access point the boot setup, on probation
    qnx/ap.sh uplink trial [SECONDS]   # the access point on bcm1 beside the hotspot link, so the Pi keeps its internet ("The uplink")
    qnx/ap.sh uplink persist     # make that the boot setup, on probation
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

### The uplink: internet on the Pi during a game

In the setup above bcm0 is the access point, so the Pi has no internet during a game. The uplink keeps bcm0 on the iPhone's hotspot as a station, with the phone's address, default route and DNS, and runs `gamemaster` on bcm1 beside it: the same 10.77.0.1, dhcpd and referee, on the hotspot's channel (the driver runs the two on one channel only). dhcpd answers only on bcm1 and still hands out no router, so the Mac reaches the Pi at 10.77.0.1 over `gamemaster`, the Pi's own internet goes out bcm0, and nothing for 10.77.0.0/24 goes to the phone. The Mac keeps its internet on USB.

bcm0 joins with the boot setup's hotspot config (`/data/var/etc/settings/wpa_supplicant.conf`, which `qnx/ap.sh revert` puts back from `~/gmnet/backup/`). `uplink persist` changes only `post_startup.sh`: one line that runs `gm-net.sh uplink boot`, backed up first to `~/gmnet/backup/uplink/`. At boot that waits up to 60 s (`UPLINK_WAIT` in `net.conf`) for the hotspot. With no hotspot, a 5 GHz one, or a bcm1 that will not run the access point, it falls back to the setup above, `gamemaster` alone on bcm0 on channel 6 without internet, so the game network always comes up; the next boot tries again. `qnx/ap.sh status` says which one this boot got, whether the uplink is up, the default route, which interface reaches the Mac, and whether the Pi reaches `https://api.anthropic.com`, which makes it a few seconds slower.

The iPhone: Settings, Personal Hotspot, turn on Allow Others to Join and Maximize Compatibility. Maximize Compatibility puts the hotspot on 2.4 GHz. Without it the hotspot is on 5 GHz, `gamemaster` would have to follow it there, and the robot (an ESP32, 2.4 GHz only) could not join, so the Pi falls back instead. Keep that screen open while the Pi boots: an iPhone can stop showing its hotspot when nothing has used it for a while. On 2.4 GHz the robot can see the hotspot too, so the robot must not have it saved (README, "Setting up the robot").

The channel is set at boot. If the hotspot goes away during a game, `gamemaster` stays up and the Pi's internet goes with the hotspot; it may come back if the phone returns on the same channel, otherwise after a reboot.

None of this has run on the Pi yet. With the Pi on:

1. The iPhone: Personal Hotspot and Maximize Compatibility on, that screen open.
2. If the Pi boots into `gamemaster` today: from `gamemaster`, `qnx/ap.sh revert`; the Pi reboots onto the hotspot. Put the Mac on the hotspot too (`scripts/wifi.sh back`, then the iPhone's network from the Wi-Fi menu). `qnx/ap.sh status` says `boot setup: the hotspot client`.
3. `qnx/ap.sh install`.
4. `qnx/ap.sh uplink trial 300`. Half a minute later `qnx/ap.sh status` shows `bcm1: 10.77.0.1 AP COMPLETED gamemaster` on the hotspot's 24xx MHz, `uplink: up`, `default route: 172.20.10.1 on bcm0`, `to the Mac (10.77.0.2): bcm1` and `internet: yes`. Join `gamemaster` from a phone: status lists it and its 10.77.0.1xx lease. The trial ends by itself after 5 minutes, or with `qnx/ap.sh revert`. If the access point does not come up (`~/gmnet/log/trial.log` on the Pi), stop here: every boot would fall back. `internet: partly ... certificate` means the network works but Python on the Pi has no CA certificates, which the referee's API calls will need; `internet: no ... no DNS from the phone` means dhcpcd did not pass the phone's DNS on.
5. `qnx/ap.sh uplink persist`, then `qnx/ap.sh reboot`.
6. A minute later, with the iPhone on the Mac's USB: `scripts/wifi.sh game`, then `qnx/ap.sh status` shows `boot setup: the uplink ... (on probation)`, `this boot: the uplink: ...` and `internet: yes`.
7. `qnx/ap.sh confirm` within 15 minutes. Without it the Pi takes its line out again and reboots onto the hotspot by itself.
8. The fallback, once: hotspot off, `qnx/ap.sh reboot`, two minutes, `scripts/wifi.sh game`; `qnx/ap.sh status` shows `this boot: the fallback: gamemaster alone on bcm0`. Hotspot on and `qnx/ap.sh reboot` to get the uplink back.

To undo it: `qnx/ap.sh revert` from `gamemaster` takes the line out of `post_startup.sh` and reboots the Pi onto the hotspot as a plain client, with no `gamemaster`. For the setup above from there, "The changeover", step 4. One boot setup at a time: `trial` and `persist` refuse while the uplink is the boot setup, and the uplink commands refuse while the setup above is.

## ssh from anywhere: the relay

The Pi keeps an outbound connection to a relay on the AWS VM (`wss://qnx.3-23-80-81.sslip.io`, port 443 only), so the Mac can ssh to it from any network while the Pi has internet (the hotspot, or the uplink beside `gamemaster`; with `gamemaster` alone on bcm0 it has none and the tunnel waits). `qnx/relay/` is [qnx-pi-headless-relay](https://github.com/lancestreuber/qnx-pi-headless-relay) at 3fedf7b.

    qnx/relay.sh ssh [CMD]   # ssh to the Pi through the relay
    qnx/relay.sh status      # the relay container on the VM, and whether the Pi answers through it

Set up once, already done: `setup` made the keys in `.qnx-connect/qnxpi` (gitignored; keep a copy, the relay and the Pi trust exactly these), `server` runs the relay in Docker on the VM behind the VM's Caddy, which also serves Tooey (one extra site at the end of `/etc/caddy/Caddyfile`; run `server` again if a Tooey deploy rewrites that file), and `install` copied the Pi's side to its boot partition, where the image's `/boot/onboot` starts it at every boot. Logs on the Pi: `/boot/qnx-onboot.log`, `qnx-supervisor.log`, `qnx-tunnel.log`.

## The status light

A red-yellow-green LED on the Pi's header shows how far the box has come up, each colour adding to the ones before: red once the Pi is on, yellow too once its Wi-Fi has an address (the hotspot or `gamemaster`), green too once the robot is on the same Wi-Fi. Green means the robot's MAC (`ROBOT_MAC` in `qnx/ap/net.conf`) answers a ping, not that the gateway on the Mac has it. A new robot needs its MAC there: it is the `device_id` in the gateway's `curl -s 127.0.0.1:8767/status`.

Wiring, with a 220-330 ohm resistor on each colour leg: red to pin 11 (GPIO17), yellow to pin 13 (GPIO27), green to pin 15 (GPIO22), the common (longest) leg to pin 9 (ground). Pin 1 is the square pad at the header's end away from the USB ports, in the row nearer the middle of the board.

    qnx/led.sh install     copy qnx/led/status-led.py to ~/gmled on the Pi and start it
    qnx/led.sh test        each colour for 2 s
    qnx/led.sh status      whether it runs, and what it last showed (~/gmled/led.log)
    qnx/led.sh boot        start it at every power-on (one line in post_startup.sh, backed up first); unboot takes it out

The pins are QNX's `rpi_gpio` files, `/dev/gpio/N` (write `out`, then `on` or `off`), which qnxuser may write as a member of the gpio group. The robot answers pings slowly (up to about a second in Wi-Fi power save), so each ping waits 2 s and three misses in a row turn the light back to yellow.
