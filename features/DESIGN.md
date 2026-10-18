# DESIGN — Game master

The orienting document for the agents that build the game master, with the humans as secondary readers. Highest altitude only. Every constraint carries `ruled` (the visionary's, citing the docket entry) or `chosen` (the agents' call). The feature files bind; this document explains. The agent holds the pen; every change appends a changelog line naming the ruling that sanctioned it; a `ruled` constraint changes only by the visionary's reversal.

## Identity

- A game master for a table of friends: it counts the table, deals private roles on its own screen, runs Mafia, Imposter and Wavelength with human-like narration, catches heads-up players at night, and takes votes by voice, so nobody has to sit out to host. [ruled: D1, D2, D14]
- Mafia is the demo; Imposter the one-minute fallback; Wavelength last. [ruled: D4, D32]
- No forfeits, no drinking-game layer. [ruled: D3]

## Shape

- Two parts and nothing else: the **body**, a StackChan CoreS3 (camera, turning head, screen, microphone, speaker), and the **brain**, a Raspberry Pi 5. No laptop, no second camera, no phone. [ruled: D29]
- Every game runs offline: the brain is its own wireless network; speech-to-text and a local voice run on the brain; no game needs the internet. Only the host's talk may use it: small-talk replies and quips from a cloud model (Anthropic's Claude by default, Gemini as the option) when a key is set, scripted lines otherwise. [ruled: D28, D40]
- Raspberry Pi OS on the brain, not QNX. [ruled: D31]
- The body streams camera frames and microphone audio to the brain and plays back audio, shows a face or a private screen, and turns its head on the brain's command; it holds no game state. [chosen]
- The brain holds all game state as deterministic code; models transcribe, synthesize and decorate, never decide. A model only writes words, and the host sounds like a person running game night, not an assistant. [ruled: D14, D42]
- The host's voice: fixed lines generated once with ElevenLabs and cached on the brain; composed lines by ElevenLabs live when a key and the internet are there, else a local voice; the two must sound like one host in the demo. [ruled: D30, D41]

## The host's senses, exactly

- Counting: one full turn of the head; faces found become seats one to N in the order found; a spoken count that disagrees stops the start until they agree. [ruled: D5, D6]
- The private screen: shown only while exactly one face is close and facing the host; blank within one second when a second face appears; back when it leaves. [ruled: D7, D8]
- Heads down: a sweep finds frontal faces; one warning by seat; a second in the same night sits the player out for the round. Eyes-open-head-down is out of reach and the rule is written so it does not matter. [ruled: D9, D10, D11]
- Votes: the head turns to each living player; each names a seat; a majority eliminates, a tie eliminates nobody; the tally is spoken before the result. [ruled: D12, D13]
- Night actions: whispers to the host's microphone; the Doctor's save cancels the Mafia's kill. [ruled: D16, D17]

## The welcome and the host's talk

- At start and on "reset", "start over" or "restart" (which ends any game): a greeting, the full count, a hello to each seat by number, a suggestion for the headcount (two Wavelength, three or four Imposter, five or more Mafia) and a question. [ruled: D38]
- After it: a yes takes the suggestion, a game's name starts that game, a headcount said with it goes through the count check; questions and small talk get a short playful reply; noise gets nothing; silence a nudge or two, then quiet. [ruled: D39]
- Seats keep their numbers, no names; the ring shows a steady listening colour while the host listens. [ruled: D43]
- One player is suggested Twenty Questions, else Wordle. The suggestion and the answer to "what games do you have?" read the games built so far (lines.MINIMUM), so a new game shows up in the welcome once it is registered; a game without a rules line gets one that states no rule. [chosen]
- The welcome and the lobby are game code (brain/games/welcome.py, brain/lobby.py), standard library only, so they run on the QNX referee; the model call runs on the Mac behind Table.chat, and the referee never touches the internet. [chosen]
- A question about a game's rules is answered from the script, never by the model, so no rule is invented; the model writes only small talk, and a line that names a seat or a number or runs long is replaced by a scripted one. [chosen]
- A game picked within two minutes of the welcome's count plays on that count: no second sweep, no count line. "Sure" counts as a yes only within twenty seconds of a question; small talk gets at most one reply every eight seconds and six per welcome; nudges come after twenty-five quiet seconds. [chosen]
- Noise is anything short of three real words, or one right after the host asked something, and never Whisper's phantoms ("you", "thank you", "oh"). [chosen]
- In test mode a reset skips the startup welcome unless it asks for it, so the bound scenarios keep their meaning. [chosen]

## Numbers the build meets

- Five players: one Mafia, one Doctor, three Villagers; seven or more: two Mafia. [ruled: D15]
- Two minutes of discussion with a one-minute call. [ruled: D18]
- Wavelength: one to ten, ten minus the distance, three rounds, the psychic rotates. [ruled: D21]

## Build choices

- The body's firmware exposes a small HTTP contract to the brain: a frame stream, an audio stream, say, face, show, turn. The brain is one Python process: vision, speech, the game engines, the voice cache, the access point setup. [chosen]
- Fixed lines are a script with variations per game; a local small model may add a quip only where the script marks a slot, and only if the Pi has the memory for it. [chosen]

## Cut order

Wavelength, then the live banter model, then Imposter. Never cut: Mafia with the private screen, heads-down catching and voice votes. [ruled: D32]

## The build's choices, amended at 03:00 after the hardware was identified

- The StackChan is M5Stack's official K151; its body software is the open-source `stackchan-mcp` replacement firmware and Python gateway, which exposes head, camera, faces, LEDs, touch, `say` and `listen` as MCP tools; the brain drives it as an MCP client. [chosen]
- The private screen is an avatar set whose six "faces" are the host's face plus role cards, loaded at runtime per game; no text rendering exists on the device. [chosen]
- Offline voice: a `cache` engine in the gateway plays the ElevenLabs-generated fixed lines; Piper (if it installs) speaks composed lines; the gateway's cloud engines are never used at play time. [chosen]
- The Pi has 8 GB, so the local banter model is a 3B-class model under Ollama. [chosen]

## Changelog

- 2026-10-18 — initial draft (scope interview, compressed; docket D1–D32; electives D28–D31).
- 2026-10-18 — signed at D37 after ratifications D34–D36; the build's amended choices added after the StackChan was identified as the official K151 (BUILD-PLAN.md PB, rewritten). No `ruled` line changed.
- 2026-10-18 — workstream W, Rex's rulings: the welcome and its conversation (D38, D39), seat numbers and the listening ring (D43), the extras deferred (D44); cloud talk amends D28 (D40), the live ElevenLabs voice amends D30 (D41), a human-sounding host whose models only write words amends D14 (D42). The Shape lines for D28, D14 and D30 restated to match.
