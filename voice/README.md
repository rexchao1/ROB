# The host's voice

What the brain plays (brain/voice.py):

- `<voice id>/<line_key>.wav`: the fixed lines, recorded once with ElevenLabs by `scripts/make-voice.py` (D30), a folder per ElevenLabs voice. `line_key` is the sha256 of the line's text with whitespace collapsed, so a line is found by its exact words. Each folder's `index.tsv` lists its recordings' keys and text. The script records only what is missing: run it again after `brain/lines.py` gains lines, and once for each voice you want recorded (`--voice-id george`, or any ElevenLabs voice id; the default is the brain's own default voice).
- `piper/en_US-lessac-medium.onnx` (and its `.onnx.json`): the local Piper voice for the lines that cannot be recorded ahead of time, such as vote tallies. `pi/install.sh` downloads it from the rhasspy/piper-voices repository on Hugging Face; it is about 61 MB.
- `lines.txt` (optional): extra lines to record, one per row, `#` for comments.

A recording plays only while its voice is the one ROB speaks in: ElevenLabs on, and that voice picked on the dashboard (or the personality's, or `--eleven-voice`). Pick another voice, or Piper, and every line is spoken by that voice, so ROB never switches voices mid-game. A line with no recording in the voice picked is spoken by ElevenLabs live, else by Piper. With neither ElevenLabs nor Piper the recordings are the only voice, so the default voice's play whatever is picked; with no recordings either, the brain refuses to start, since a host that cannot speak cannot run a game.

Recordings saved straight in `voice/` (the layout before the folders) are never played; move them into their voice's folder, or record again.
