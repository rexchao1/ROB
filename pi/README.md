# The Pi: the brain's box

The game master runs on a Raspberry Pi 5 (8 GB) with no internet: the Pi is its own Wi-Fi network, the StackChan joins it, and the gateway, speech recognition, the voice and the banter model all run on the Pi.

## Set it up, in this order

1. **Install** (once, with Ethernet plugged in for the downloads), from a clone of the repository:

       cd gamemaster
       pi/install.sh                 # add --with-ollama for the banter model (about 2 GB)

   It installs the gateway (`stackchan-mcp 0.18.0` with faster-whisper), the brain's `.venv`, the Piper voice into `voice/piper/`, the settings file `/etc/gamemaster/gamemaster.env`, and enables two services. Check `VISION_HOST` in the settings file: it must be the Pi's address on the network the robot is on (10.42.0.1 on the hotspot).

2. **The hotspot:** `sudo pi/hotspot.sh <password>` turns the Pi's Wi-Fi into the `gamemaster` network (2.4 GHz, the Pi at 10.42.0.1). It comes back on every boot. `sudo pi/hotspot.sh --off` undoes it.

3. **Join the robot to it** (once): the stackchan-mcp firmware's Wi-Fi setup portal (join the robot's own setup network and open `http://192.168.4.1`), then choose `gamemaster` and the password. The robot finds the gateway by mDNS (`_stackchan-mcp._tcp.local.`) on the same network.

4. **Start the gateway**, then check the robot is connected:

       sudo systemctl start stackchan-gateway
       curl -s http://127.0.0.1:8767/healthz          # {"ok": true}
       curl -s http://127.0.0.1:8767/status           # "esp32_connected": true once the robot is in
       journalctl -u stackchan-gateway -f             # if it is not

5. **Start the brain:** `sudo systemctl start gamemaster-brain`, then say "let's play Mafia". Logs: `journalctl -u gamemaster-brain -f`.

Both services start on boot after step 1, so after the first time it is: power on the Pi, power on the robot, wait for the robot's face, play.

## The status light

An RGB LED on the Pi shows how far it has come up: red when the Pi is on, yellow when the Wi-Fi is up, green when the robot is connected. Wire it with a 220-330 ohm resistor on each colour leg: red to GPIO17 (pin 11), green to GPIO27 (pin 13), blue to GPIO22 (pin 15, unused), and the long leg to ground (pin 9). `install.sh` enables it as `status-led`; to try it by hand, `python3 pi/status-led.py`. For a red-yellow-green LED instead, put `LED_YELLOW=<the yellow leg's GPIO>` in the settings file. Red shows once the service starts, about 10-20 seconds after power-on.

## Recorded voice

The fixed lines sound best recorded with ElevenLabs. On a machine with internet, from the repository root: `ELEVENLABS_API_KEY=... .venv/bin/python scripts/make-voice.py --voice-id <id>`, then copy `voice/*.wav` to the Pi's `voice/` folder. Lines that are not recorded are spoken by Piper.

## Developing on a laptop instead

The same pieces run on the laptop with the robot on the laptop's Wi-Fi: `uv tool install 'stackchan-mcp[stt-faster-whisper]==0.18.0'`, then `VISION_HOST=<the laptop's LAN address> "$(uv tool dir)/stackchan-mcp/bin/python" scripts/gateway.py serve --transport streamable-http` (the gateway with each listen ending when the talker stops; plain `stackchan-mcp serve` works too, but every listen then runs its whole window), and `npm run brain -- --gateway http://127.0.0.1:8767/mcp --pcm http://127.0.0.1:8766/pcm --voice-dir voice --piper-model voice/piper/en_US-lessac-medium.onnx`.

## Not verified here

These scripts were written on a Mac and checked with shellcheck, not yet run on a Pi: the apt package names on Trixie, the hotspot on the Pi's radio, the gateway's faster-whisper wheels on aarch64, and the robot joining the hotspot.
