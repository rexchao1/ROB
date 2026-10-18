# The host's voice

What the brain plays (brain/voice.py):

- `<line_key>.wav`: the fixed lines, recorded once with ElevenLabs by `scripts/make-voice.py` (D30). `line_key` is the sha256 of the line's text with whitespace collapsed, so a line is found by its exact words. `index.tsv` lists each recording's key and text. The script records only what is missing: run it again after `brain/lines.py` gains lines.
- `piper/en_US-lessac-medium.onnx` (and its `.onnx.json`): the local Piper voice for the lines that cannot be recorded ahead of time, such as vote tallies. `pi/install.sh` downloads it from the rhasspy/piper-voices repository on Hugging Face; it is about 61 MB.
- `lines.txt` (optional): extra lines to record, one per row, `#` for comments.

A line with no recording is spoken by Piper. With neither a recording nor Piper, the brain refuses to start, since a host that cannot speak cannot run a game.
