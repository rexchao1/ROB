# DESIGN — Game master

The orienting document for the agents that build the game master, with the humans as secondary readers. Highest altitude only. Every constraint carries `ruled` (the visionary's, citing the docket entry) or `chosen` (the agents' call). The feature files bind; this document explains. The agent holds the pen; every change appends a changelog line naming the ruling that sanctioned it; a `ruled` constraint changes only by the visionary's reversal.

## Identity

- A game master for a table of friends: it counts the table, deals private roles on its own screen, runs Mafia, Imposter and Wavelength with human-like narration, catches heads-up players at night, and takes votes by voice, so nobody has to sit out to host. [ruled: D1, D2, D14]
- Mafia is the demo; Imposter the one-minute fallback; Wavelength last. [ruled: D4, D32]
- No forfeits, no drinking-game layer. [ruled: D3]

## Shape

- Three boxes: the **body**, the StackChan K151 (camera, turning head, screen, microphone, speaker, light ring, head touch) running the stackchan-mcp firmware and gateway; the **brain** in two parts, a Mac (the gateway, speech-to-text, the voice, vision, the host) and a Raspberry Pi running QNX (the referee: the rules, the lobby, the parsing; and the game's own Wi-Fi network). No phone, no second camera. [ruled: D29, amended by D45]
- Every game runs offline: the brain is its own wireless network; speech-to-text and a local voice run on the brain; no game needs the internet. Only the host's talk may use it: small-talk replies and quips from a cloud model (Anthropic's Claude by default, Gemini as the option) when a key is set, scripted lines otherwise. [ruled: D28, D40]
- Proposed (review R, unratified): the referee's Table takes calls only with a required shared token, and no call may hold it longer than the gateway's longest listen. [ruled: D85]
- The Pi runs QNX and stays on it: the referee and the access point are standard-library Python; speech-to-text, the voice and vision, which have no QNX port, run on the Mac and serve the Table over HTTP. [ruled: D31, amended by D46]
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

- At start and on "reset", "start over" or "restart" (which ends any game): a greeting that asks what they want to play or how many they are, and the host listens straight away. No sweep on its own (Rex, 2026-10-18: the opening count felt hardcoded and deaf). [ruled: D38, revised]
- After it: a headcount said out loud is taken at its word (seats spread evenly for turning) and gets a suggestion (two Wavelength, three or four Imposter, five or more Mafia); "count us" or "look around" gets the full sweep, a hello to each seat and the suggestion; a yes takes the suggestion; a game's name starts that game, on the count so far, or with a count said with it. Only a game started with no number at all sweeps, and only a number that disagrees with a sweep goes through the count check. Questions and small talk get a short playful reply; noise gets nothing; silence a nudge or two, then quiet. [ruled: D39, revised]
- Seats keep their numbers, no names; the ring shows a steady listening colour while the host listens. [ruled: D43]
- One player is suggested Twenty Questions, else Wordle. The suggestion and the answer to "what games do you have?" read the games built so far (lines.MINIMUM), so a new game shows up in the welcome once it is registered; a game without a rules line gets one that states no rule. [chosen]
- The welcome and the lobby are game code (brain/games/welcome.py, brain/lobby.py), standard library only, so they run on the QNX referee; the QNX referee calls the talk model when it has internet and a deliberately installed key, falling back to the Mac's Table.chat otherwise. It mirrors the Mac's talk choices in RAM. Only selected group facts and public game totals are durable on the Pi, outside deployed code; dialogue stays bounded in RAM and clears on reset, game end and exit. [chosen]
- A question about a game's rules is answered from the script, never by the model, so no rule is invented; the model writes only small talk; a line that runs long is cut to the sentences that fit, and one that names a seat or a number is replaced by a scripted one. [chosen]
- A game picked within two minutes of the welcome's count plays on that count: no second sweep, no count line. "Sure" counts as a yes only within twenty seconds of a question that offered the game; small talk gets a reply every time (at most one a second), with the last dozen lines of the lobby talk as its memory; nudges come after twenty-five quiet seconds. [chosen]
- Noise is anything short of three real words, or one right after the host asked something, unless it is a greeting or a word to ROB ("hello", "what's up", "hey rob"); never Whisper's phantoms ("you", "thank you", "oh"), a phrase repeated over and over, or a run-on past forty words. [chosen]
- In test mode a reset skips the startup welcome unless it asks for it, so the bound scenarios keep their meaning. [chosen]

## Pausing and the quiet lobby

- "Pause" at any listen holds the game and its clock; "resume", a head tap or the page's Resume carries on and the interrupted listen runs again; a stop or a reset said while paused is heard. [ruled: D72]
- After thirty quiet seconds the lobby listens in ten-second windows, because the robot chimes each time its microphone opens. [ruled: D73]

## The host's character

- The host is ROB and says so only when asked. [ruled: D76]
- Every model line passes the house rules (two sentences, about fifteen words, no assistant phrases, no emoji, one exclamation mark, no seat named) or a scripted line is said instead; a slow answer is a scripted line. [ruled: D74]
- Six personalities (friendly, sarcastic, energetic, calm, dramatic, grumpy) change the talk's style, the ring's colour and the voice, never a rule or a ruled line; five ElevenLabs voices; both kept across starts. [ruled: D75, D77]

## More games, for small tables

- Twenty Questions for one player or a group as one, either way round; the host counts out loud only at ten, fifteen and the last question; a hint costs a question; the built-in table answers where it can and a model answer never outranks it. [ruled: D61, D62, D63, D64, D65]
- Hot Seat for two or more: five seconds in the first round, a second less each round, never under three; out on silence, a pass, a repeat or an answer that does not count; a tie after twelve rounds. [ruled: D66, D67, D68]
- Wordle, out loud, for one or more: six guesses said or spelled, feedback spoken short with the heard word first, a word not known uses no guess, the last guess confirmed, turns for a group; the grid reaches the dashboard, not the robot's screen. [ruled: D69, D70, D71]
- Every game plays offline from its built-in tables; a model only words a question or picks from a fixed set of answers. [ruled: D42, D63]
- Proposed (review R, unratified): short sound cues at the script's marked moments, never under speech, CC0 or generated once and cached, off with one flag, deciding nothing (`docs/SOUND-CUES.md`). [ruled: D108]
- The talk reaches the model with a request shaped per model; the page's AI tab shows provider, model, effort, the last result and a Test button; ROB's tab holds personality, voice and speaker. [ruled: D113]
- Proposed (review R, unratified): a model advises, code decides: a Twenty Questions guess wins only by naming the secret; a Hot Seat answer the model doubts is put to the table. [ruled: D104]

## The operator's dashboard

- One page on the brain's HTTP server, reachable from a phone on the game's network: the game as it happens, polled about once a second, nothing from the internet. [ruled: D78]
- Every in-game button is a phrase the robot understands by voice, sent as typed hearing that the next listen drains before the microphone. [ruled: D79]
- API keys are written to the brain's environment file and never shown again; a request from another site is refused. [ruled: D80]
- Tuning applies live and is saved beside the brain; a saved setting overrides the matching flag; the volume is the robot's own and is never saved. [ruled: D81]
- Proposed (review R, unratified): every write from the page carries a secret minted at this start; answers are readable by the page's own origin only; rigging is test-mode only. [ruled: D86]
- The brain serves two pages today, `/dashboard` (workstream X: personality, talk, voice, games, the feed) and `/dash` (the dashboard plan: lobby, game screen, settings drawer, keys, tuning). The plan names one. [chosen]

## Numbers the build meets

- Five players: one Mafia, one Doctor, three Villagers; seven or more: two Mafia. [ruled: D15]
- Two minutes of discussion with a one-minute call. [ruled: D18]
- Wavelength: one to ten, ten minus the distance, three rounds, the psychic rotates. [ruled: D21]
- Hot Seat: five seconds, then four, then three, never under three; twelve rounds at most. [ruled: D66, D68]
- Twenty Questions: twenty questions; the welcome's nudges at twenty-five seconds; the game's at eight and twenty, gone at three minutes. [ruled: D56, D64, D65]

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
- 2026-10-18 — review R (Linus): Rex's reversal of D29 and D31 recorded as amendments D45 and D46 and the Shape lines restated; the welcome's lines (D47 to D60), the three new games (D61 to D71), pausing (D72, D73), the host's character (D74 to D77) and the dashboard (D78 to D81) added as the build's record, each awaiting Rex's ratification; the fence gained D82 to D84. The two `ruled` lines changed here changed on Rex's reversal, not the agent's call.
- 2026-10-18 — review R, proposals (D85 to D107, all unratified): the Table's token and the page's secret (D85, D86), a model advises and code decides (D104); the amendments proposed to D5, D6, D12, D16, D21, D33 and D72 are in the docket and in the scenarios held in the wip register, and change no `ruled` line here until Rex rules.
- 2026-10-18 — Rex's commit 3ae4edc transcribed (D109 to D113): a lean-in answered by voice or a tap, pause by `shut up` or a bare `stop` (D110 replaces the review's D93 list), the speaker by voice, `say that again` (leaves D83), the talk's request shape and the AI tab.
