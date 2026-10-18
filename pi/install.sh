#!/usr/bin/env bash
# Set up the game master on a Raspberry Pi 5 (Raspberry Pi OS Bookworm or Trixie, 64-bit):
# the StackChan gateway, the brain's Python environment, the local voice, optionally
# the banter model, and the two systemd services. Run it as your normal user from a
# clone of the repository, with internet (Ethernet, before pi/hotspot.sh takes the Wi-Fi):
#
#   pi/install.sh [--with-ollama] [--no-services]
#
# Safe to run again: every step skips what is already there.
set -euo pipefail

WITH_OLLAMA=0
SERVICES=1
for arg in "$@"; do
  case "$arg" in
    --with-ollama) WITH_OLLAMA=1 ;;
    --no-services) SERVICES=0 ;;
    *) echo "usage: $0 [--with-ollama] [--no-services]" >&2; exit 2 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the repository root
GATEWAY_VERSION="0.18.0"
PIPER_VOICE="en_US-lessac-medium"
PIPER_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium"
step() { printf '\n== %s\n' "$*"; }

if [[ $EUID -eq 0 ]]; then
  echo "run this as your normal user; it uses sudo where it must" >&2
  exit 1
fi

step "apt packages"
sudo apt-get update
# libopus0: the gateway encodes the voice to Opus for the robot. network-manager: hotspot.sh.
sudo apt-get install -y curl git ca-certificates libopus0 network-manager avahi-daemon

step "uv"
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

step "the gateway, stackchan-mcp $GATEWAY_VERSION (speech recognition only; the brain plays its own voice through /pcm)"
uv tool install --force "stackchan-mcp[stt-faster-whisper]==$GATEWAY_VERSION"
GATEWAY_PY="$(uv tool dir)/stackchan-mcp/bin/python"

step "the speech recognition model (faster-whisper base.en), fetched now so the first game is not slow"
"$GATEWAY_PY" -c "from faster_whisper import WhisperModel; WhisperModel('base.en', device='cpu', compute_type='int8')"

step "the brain's Python environment"
cd "$REPO"
if [[ ! -x .venv/bin/python ]]; then
  uv venv --python 3.11 .venv
fi
uv pip install --python .venv/bin/python -r pyproject.toml --extra voice

step "the local voice (Piper $PIPER_VOICE)"
mkdir -p voice/piper
for f in "$PIPER_VOICE.onnx.json" "$PIPER_VOICE.onnx"; do
  if [[ ! -s "voice/piper/$f" ]]; then
    curl -fL -o "voice/piper/$f.part" "$PIPER_URL/$f"
    mv "voice/piper/$f.part" "voice/piper/$f"
  fi
done
.venv/bin/python -c "
from pathlib import Path
from brain.voice import PiperVoice, seconds
print('piper ok:', round(seconds(PiperVoice(Path('voice/piper/$PIPER_VOICE.onnx')).pcm('Five of you.')), 2), 's')"

if [[ $WITH_OLLAMA -eq 1 ]]; then
  step "the banter model (Ollama, llama3.2:3b)"
  if ! command -v ollama >/dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
  fi
  ollama pull llama3.2:3b
fi

step "settings in /etc/gamemaster/gamemaster.env"
sudo mkdir -p /etc/gamemaster
if [[ ! -f /etc/gamemaster/gamemaster.env ]]; then
  sudo install -m 600 -o "$USER" "$REPO/pi/gamemaster.env.example" /etc/gamemaster/gamemaster.env
  echo "wrote /etc/gamemaster/gamemaster.env from the example"
else
  echo "kept the existing /etc/gamemaster/gamemaster.env"
fi

if [[ $SERVICES -eq 1 ]]; then
  step "systemd services"
  sed -e "s|@USER@|$USER|g" -e "s|@HOME@|$HOME|g" "$REPO/pi/stackchan-gateway.service" | sudo tee /etc/systemd/system/stackchan-gateway.service >/dev/null
  sed -e "s|@USER@|$USER|g" -e "s|@REPO@|$REPO|g" "$REPO/pi/gamemaster-brain.service" | sudo tee /etc/systemd/system/gamemaster-brain.service >/dev/null
  sudo systemctl daemon-reload
  sudo systemctl enable stackchan-gateway.service gamemaster-brain.service
  echo "enabled; start them with: sudo systemctl start stackchan-gateway gamemaster-brain"
fi

step "done"
echo "next: sudo pi/hotspot.sh <password>, then join the robot to the gamemaster network (pi/README.md)"
