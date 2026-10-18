# Out of scope — Game master

The fence for the game master, scoped 2026-10-18 in a deliberately short interview (the visionary declined the checklist sweep and the adversarial pass; the boundary question was not put). Every entry cites the docket ruling it came from and the date it was ratified. Bound scenarios touched: none (a new project). Entries from D82 on were added by the review of 2026-10-18 from the build's own record (BUILD-PLAN.md, DASHBOARD-PLAN.md) and await Rex's ratification.

## Declined

- **Forfeits and drinking-game penalties.** The host never assigns a penalty for losing a round. (D3, 2026-10-18)
- **The checklist sweep, every category.** Usability, reliability, availability, performance, security, ops burden, diagnosability, evolvability, lifecycle and compliance, declined in bulk, unprobed. (D22, 2026-10-18)
- **The adversarial pass.** No objection to the corpus was put or answered. (D23, 2026-10-18)

## Deferred — each with its reopening condition

- **Wavelength, then the live banter model, then Imposter**, in that order, if the build runs short; Mafia with the private screen, heads-down catching and voice votes is never cut. Nothing was cut: all three were built and bound before the deadline, so the review proposes closing this deferral and keeping D32's cut order for a future build. (D33, closed by D107 proposed, 2026-10-18)

- **Head pats, "louder" and "quieter", sound and mood, playing again with scores, players' names.** Asked for after the welcome; seats keep their numbers meanwhile. Reopens when Rex picks one up after trying the welcome on the robot. (D44, 2026-10-18)

- **Scripted lines per personality, the one callback to a moment from earlier in the game, switching the personality by voice.** Workstream X built the five personalities as a talk style, a ring colour and a voice; these three were left. Reopens when Rex picks one up. (D82, 2026-10-18)

- **"Say that again", "count again", "more time" with a deadline the page can show, taking back a wrong heads-up warning, a `listening_for` field in the reported state.** The robot should do each by voice first; the page leaves them out until it can. Reopens one by one as the robot learns the phrase. (D83, 2026-10-18)

- **The Wordle grid on the robot's own screen.** Rex asked for it in green, yellow and gray; the build reports the board to the dashboard only. Reopens when a `show_board` for the robot's screen is built. (D84, 2026-10-18)

## Named assumptions

- **Seats and light.** Players stay in their seats and the table is lit well enough to find faces at about a metre. Reopens if the demo table needs a lamp or players move. (D25, 2026-10-18)
- **Whispers are private.** A night whisper reaches the host's microphone and not the other players; if the host cannot make it out it asks once more, quietly. Reopens if a whisper is overheard or missed at the demo table. (D26, 2026-10-18)
- **The host's rulings stand.** A warning or a tally is not changed on dispute; the group may restart the round by saying so. Reopens if disputes are frequent. (D27, 2026-10-18)

## Out of reach by construction — stated so nobody expects it

- **Who is actually peeking with eyes open and head down.** The host finds frontal faces; a player with their head down and eyes open is not caught. The heads-down rule exists so that a face is the thing being looked for. (D9, D10, 2026-10-18)
- **Anything said while the host's microphone is off or the room is loud.** A vote or a whisper the host does not hear is asked for again; nothing is inferred. (D12, D26, 2026-10-18)

## Roads not taken

- Private roles by text message to each player's phone; rejected for the private screen with the one-face lock, which needs no phone numbers. (D7, 2026-10-18)
- A second camera at table level for eyes-closed detection and raised-hand votes; rejected for the StackChan's own camera alone, which made heads-down and voice votes the rules. (D9, D12, D29, 2026-10-18)
- The brain wholly on QNX; rejected at scoping for Raspberry Pi OS, then half taken after all: the Pi runs QNX as the referee and the access point while speech and vision run on a Mac. (D31, amended by D46, 2026-10-18)
- A laptop or a phone hotspot as part of the product; rejected for the brain being its own network, which the QNX Pi now hosts; the Mac is part of the brain, not a laptop at the table. (D28, D29 amended by D45, 2026-10-18)
