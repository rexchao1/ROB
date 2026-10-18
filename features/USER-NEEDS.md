# User needs — Game master

The needs ledger for the game master, reconciled from the interview record on 2026-10-18. Every need is an N entry in `DOCKET.md`. The ledger explains and prioritizes; it never specifies. At build, only the feature files bind.

Beneficiary: **user** is the group of friends at the table; the visionary and their teammate are also players.

## Needs

- **N1** (user, wt 5) — *I need my friends to be able to play games like Mafia, Imposter and Wavelength without allocating one person the role of game master and forcing them to sit out, so everyone is involved in the game, with human-like narration and banter.* The vision, in the visionary's words. Means, ruled: the body is a StackChan CoreS3 and the brain a Raspberry Pi 5, nothing else (D29); the host's fixed lines are ElevenLabs voices cached on the brain, live lines ElevenLabs when online and a local voice otherwise (D30, amended by D41). Evidence: D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12, D13, D14, D15, D16, D17, D18, D19, D20, D21, D22, D23, D24, D25, D26, D27, D28, D29, D30, D31, D32, D33, D38, D39, D40, D41, D42, D43, D44 — every ruling in the record serves this one need. Coverage: `scenario` — hosting.feature, mafia.feature, imposter.feature, wavelength.feature; plus `structural` for D14, D28, D31, D32 and the welcome's D38 to D43 in DESIGN.md (not yet in a feature file: Rex is trying the welcome by hand first); plus `absence` for the declined forfeits (D3). Coverage note: the "human-like narration and banter" half of the need is `structural` (D14: scripted flavor plus an optional local quip) because no scenario can assert that a line is human-like; the scenarios assert only that the ruled lines are said.
