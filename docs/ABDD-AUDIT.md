# audit — rexchao1/ROB — 2026-10-18 06:00 PDT

question: where are we really? [derived]        filters: none
instrument: judge Claude Fable 5.1 · audit 0.1.4 · no clerk · gherkin-node-test 0.11.0 · docketry 0.1.0 · gherkin-trace 0.1.0 (refused, see evidence)
invoker: human (Linus, the original visionary, asked for a review with tracking); both faces render
snapshot: branch `abdd/1-gaps` on top of `2d9992c` (Rex, 2026-10-18 05:14); the contract additions of this branch are part of the snapshot and are named as such below

This report is pull-based and point-in-time. It judges state and never gates: counts, per-unit states with pointers, findings with pointers, one ranked list. The conformance-record entry (step 9 of the protocol) is not written: it needs the human's ratification of the report first.

⚠ design↔code was DRIFTING at `2d9992c` — the plan no longer described the build
  DESIGN.md still ruled "two parts, no laptop" (D29) and "Raspberry Pi OS, not QNX" (D31) while README and BUILD-PLAN shipped three boxes with a QNX referee; the reversal was recorded only in `docs/BUILD-PLAN.md` ("Rex's decisions, 2026-10-18 00:15 … Linus to be told") and never back-propagated. This branch records it as amendments D45 and D46 and restates the two Shape lines; both amendments are unratified (`docketry lint`: D45 `rewrite`, 45 `inferred`), so the drift is now *recorded*, not *closed*.

## Evidence basis

- features: 11 files, 106 scenarios after outline expansion (4 signed files, 28 scenarios; 7 files added by this branch from the built code, 78 scenarios); one batch
- run manifest: present, declared `{"run-manifest":1}`, regenerated on this branch by `npm run manifest` — 28 `passed`, 78 `unbound`
- wip register: `test/features.test.ts` L24 — the 7 new basenames; the 4 signed files are not in it
- definer map: `test/features.test.ts` L26 — hosting, imposter, mafia, wavelength → `test/steps/<name>.steps.ts`
- ledger: `features/USER-NEEDS.md` — N1 (signed), N2 and N3 (added by this branch, `[I]`)
- DESIGN.md: present, `ruled`/`chosen` tags and a changelog (4 lines after this branch)
- fence: `features/OUT-OF-SCOPE.md` beside the features; no shadowed root file
- docket: `features/DOCKET.md` — 87 entries, D1–D37 signed, D38–D44 Rex's `[V]`, D45–D84 this branch's `[I>V]`/`[I]`; strict lint 46 findings, all provenance (ratification pending) plus D45 `rewrite`
- git: 2 commits before this branch (`f758799` 04:57, `2d9992c` 05:14, both Rex Chao); the whole build landed in one commit, so commit-level history of the build is thin
- gt refused: "no picture exists yet — a refresh builds one" — watcher dark; remedy noted under readiness (`gt refresh --root .`, run by the owner, never by the audit); cino:spec dark
- journal dark: the treecontext store on this machine is bound to the reviewer's repo (LAHacks_AI_2026), not to ROB — provenance of the build sessions dark, changelog citations unverifiable
- no register; no archive: pre-clerk run
- design tier (`features/design/`): absent
- centrality: from the ledger (N1 wt 5; N2, N3 wt 3 as the reviewer's guesses)
- unit tests: 404 passed, 1 skipped (`npm test` at `2d9992c`, 2026-10-18 05:29) — cited as the run's green, never redone
- cold reviews feeding the features↔code grades: four reviewer passes of 2026-10-18 (mutation probes and step honesty; rules versus docket; runtime and security; the untested W/X code), summarised in `docs/REVIEW-2026-10-18.md` on the next branch (`abdd/2-proposals`)

## EDGES

needs↔features  3/3 covered — N1 by hosting, mafia, imposter, wavelength (bound) and welcome, pausing, host-character (wip); N2 by twenty-questions, hot-seat, wordle (wip); N3 by operator-dashboard (wip). Orphan files: none. Needs validated by proxy: N2, N3 — inferred by the reviewer from Rex's recorded rulings, no reading or feedback from Rex yet (ledger rows say so); N1's "human-like narration and banter" half is `structural` by the ledger's own note and no scenario asserts it.

features↔code   28 claimed / 24 solid — 4 flagged (thin 1, cino:assertion 3); 78 has-contract (wip). Obligatory probes a–d caught; probes e (plurality), m (host plays on after the win), s (doubled warning) missed

design↔code     DRIFTING at `2d9992c`, RECORDED on this branch — constraint by constraint:
  - "Two parts and nothing else … No laptop" [ruled: D29] — contradicted by README L5/L34 (Mac + QNX Pi + robot), `brain/remote.py`, `qnx/`; ruling landed elsewhere (`docs/BUILD-PLAN.md` "Rex's decisions"); restated on this branch under D45
  - "Raspberry Pi OS on the brain, not QNX" [ruled: D31] — contradicted by `qnx/README.md`, `brain/referee.py`; same home; restated under D46
  - "runs Mafia, Imposter and Wavelength" (Identity, D1/D2/D14) — honored, overstated: `brain/games/__init__.py` L52–60 registers hotseat, wordle and twenty as well; D2 bounds scope to three games and no fence entry widened it before this branch (N2, D61–D71 now record it, unratified)
  - "Counting: one full turn of the head" [ruled: D5] — contradicted: the head sweeps −90..90 (`brain/host.py` `_sweep`, `brain/vision.py` `sweep_pans`); the binding redefines "a full circle" as the sweep (`test/steps/hosting.steps.ts` L52–54); BUILD-PLAN "Sweeping (03:30)" records the fact; D5's text was not amended
  - "models … never decide" [ruled: D14, D42] — honored for the four signed games (quip/chat return nothing the rules read); contradicted by `brain/games/hotseat.py` `judge()` (a model's yes/no eliminates a player when the answer is on no list) and softened by `brain/games/twenty.py` `_answer()` (the model answers about the secret where the table lacks the trait); recorded as D67 and D63 on this branch, flagged for Rex
  - "fixed lines generated once with ElevenLabs and cached on the brain" [ruled: D30, D41] — not built: no recordings exist (`voice/README.md`, BUILD-PLAN C "330 lines to record once there is an ElevenLabs key"); Piper speaks everything unless a live ElevenLabs key is set
  - "Every game runs offline" [ruled: D28, D40] — honored: the referee is standard library; talk is the only network use and falls back (`brain/talk.py` `_ask`)
  - "The private screen … blank within one second" [ruled: D7, D8] — honored (`brain/host.py` POLL 0.25 s)
  - "Votes: a majority eliminates, a tie eliminates nobody" [ruled: D12, D13] — honored, with an unruled third outcome (no majority, `brain/lines.py` `no_majority`) that no scenario names
  - Build choices marked `[chosen]` at 03:00 ("a cache engine in the gateway", "the Pi has 8 GB, so the local banter model is a 3B-class model under Ollama") — stale: the voice is the brain's (BUILD-PLAN "The voice is the brain's"), the Pi runs QNX and Ollama runs on the Mac
  - changelog vs git: `2d9992c` (pause, the quieter lobby, ROB's name and voices) touched behaviour the plan calls ruled (D38's welcome lines, the host's ring under D43) with no changelog line and no docket entry before this branch (D72–D77 now)
  - companion documents: `docs/BUILD-PLAN.md` header said "D1–D33; signature pending" after D37 signed; README still described `/dashboard` and `/dash` as one dashboard in two sentences while the brain serves two pages (`brain/dashboard.py`, `brain/dash.py`); both noted, the header fixed on this branch

needs↔design    dark — the design's `ruled` tags cite rulings (D#), never needs (N#); the ledger's N1 row names its means (D29, D30) itself. Heavyweight need N1 has constraints throughout; N2 and N3 are represented only by this branch's additions.

## UNITS  (has-contract 78 · built 28 · in-review 0 · complete 0 · regressed 0)

No unit is `complete`: D37 signed the *contract* before code existed (a scoping ratification), and no review of a *binding* has been recorded in the fence, the ledger or a journal. Every green manifest row therefore places at `built`. No unit is `regressed`: nothing was ratified as bound and then failed.

**built (28)** — manifest rows `passed`; graded on the features↔code edge from the bindings and from the mutation pass of 2026-10-18 (worktree at `2d9992c`; probe letters below are that pass's). Flags: thin 1 · cino:assertion 3 · 24 solid. The four probes `docs/BUILD-PLAN.md` "Acceptance bars" made obligatory were all caught (a, b, c, d).

| unit (file :: title) | grade | why, and the pointer |
|---|---|---|
| hosting :: The host counts the table and numbers the seats | solid | photo yaws −90 → 90, increasing, gaps under the field of view, read from the fake's `move_head` record (`test/steps/hosting.steps.ts` L52–65); the count line far side. Note: the binding reinterprets "a full circle" as the sweep (L52–54 comment) — the sentence does not match the code (needs-work 3) |
| hosting :: A spoken count that disagrees with the host's count stops the start | solid | the mismatch line far side (probe g red); "no game has started" decided by `/test/state` `game === null` (L76, probe g2 red), which the plan sanctions for named state. Rider unearned: L77 (no "lean in" heard) cannot fire because the clock is not advanced after the mismatch (probe g3 green with L76 removed) |
| hosting :: Leaning in shows one player their private screen | solid | the fake's screen before, during and after the lean-in (`common.ts` L390–395); probe t2 (card up before anyone is close) red |
| hosting :: A second face blanks the private screen | solid | blank within 1.0 s of the two-face table, polled at 0.25 s on the fake's screen (L105–119); probes a and a2 red |
| hosting :: The private screen returns when the second face leaves | solid | the fake's screen with the head on seat two; probe a red |
| hosting :: A face up during heads down is warned by seat | solid | the warning line far side (L150–152); "one warning" from `/test/state` (sanctioned). Note: a doubled line passes (`toContain`, probe s green) — the far side is never asked how many times |
| hosting :: Every head down means no warning | solid | absence earned: the same scenario's world has a frontal-face control in the sibling scenario and the deciding line check fails on probe b (warn with every head down → red) |
| hosting :: A second peek in the same night sits the player out for the round | solid | the sit-out line, then the far side carries the rule: the vote asks `[1, 2, 5]` hard-coded and the morning line (probes f, f2, f3 red even with the state line removed) |
| hosting :: A majority vote by voice eliminates a seat | **thin** (by fixture) | 3 of 5 is a majority and a plurality: probe e (majority → plurality) left every scenario green. The tally and "you're out." lines are far side and real (probe h2 red); the fixture erases the failing world of the word "majority" (needs-work 8, proposal D97) |
| hosting :: A tied vote eliminates nobody | solid | the tie line and "still in" (far side "you're out." filter plus state); probes c, c2 red. Note: c was caught partly by the majority branch, not the tie branch |
| mafia :: Roles are dealt one at a time through the private screen | solid | seat order from "Player N, lean in." lines, yaw from `move_head`, cards from the fake's screen (`mafia.steps.ts` L51–59); probe t2 red |
| mafia :: The Mafia's target dies when the Doctor saves someone else | solid | the morning line far side (L82); probe d red |
| mafia :: The Doctor saves the Mafia's target | solid | "Nobody died last night." far side; probe d red. Note: "every player is still in" is state only (L98–100) |
| mafia :: Discussion time runs by the clock [1] | solid | the halfway line not before its mark (`notBefore`, L123–133) and at it; probes i (early) and i2 (late) red |
| mafia :: Discussion time runs by the clock [2] | solid | as above for "Time. Let's vote." |
| mafia :: The eliminated player's role is revealed | solid | the reveal line far side; no When, so `heard()` is the whole record (harmless: the line is unique) |
| mafia :: The village wins when no Mafia is left | **cino:assertion** | the win line is far side and real, but "the game is over" is `/test/state` `over === true` (L168–170): probe m (win said, `finish()` called, host plays on into another night) left the scenario green. The foreign system that should have been asked is the fake's record: no host line after "Good game, everyone." |
| mafia :: The Mafia win when they equal the rest | **cino:assertion** | as above; also "the host checks the win condition" is a state poll (L159–166) — the win was said during the Given's third kill |
| imposter :: Words are dealt and one player sees IMPOSTER | solid | cards from the fake's screen (`imposter.steps.ts` L30–34); probe t2 red |
| imposter :: Each player gives one clue in seat order | solid | the "one word." asks and their yaws (L66); probe r (Player one asked twice) red |
| imposter :: Voting out the Imposter ends the round with a reveal | solid | the reveal line far side |
| imposter :: Voting out anyone else lets the Imposter survive | solid | the survive line far side |
| wavelength :: The psychic alone sees the target | solid | card text and sub from the fake's screen (`wavelength.steps.ts` L70–72); probe t2 red |
| wavelength :: A spoken guess scores by distance from the target [1]–[4] | solid (4 units) | the points line far side per row |
| wavelength :: The psychic rotates and the total is announced after three rounds | **cino:assertion** | the total line and the played rounds' psychics are far side (L100–105, seats from "lean in." lines); "the next round would be Player three" is `/test/state` `next_psychic` (L106, probe n caught only there), and the scenario is made consistent with the Background by rigging psychic 5 so that Player two leads round three (L4–7) — the world was fitted to the sentence (needs-work, proposal D103) |

Given hygiene, noted not flagged: the expected voter lists for "turns to each living player in turn" come from `/test/state` (`hosting.steps.ts` L265–267, `common.ts` L484–488), so a brain that reported a wrong `living` and asked exactly those seats would agree with itself (D11's list is hard-coded, sound); "Player one quietly says …" cannot bind *who* whispered (the fake's microphone has no speaker), so the binding checks the rig instead (`mafia.steps.ts` L70–77). No pre-seeding: `/test/*` offers reset, table, frame, hear, advance, rig, state (`brain/server.py` L173–198); every mid-game Given plays the game to that point.

**has-contract (78)** — the seven files this branch added, all in the wip register (`test/features.test.ts` L24), manifest rows `unbound`. They are weaker than the rung assumes: the rung expects a *ratified* scenario, and these are the reviewer's transcription of the built code under unratified rulings (D47–D81, `[I]`/`[I>V]`). Their honest move is two clearing moves, not one: Rex ratifies or vetoes each ruling, then the bindings are written.

| file | scenarios | rulings cited | ratification state |
|---|---|---|---|
| welcome.feature | 23 (incl. an outline of 6) | D47–D60, D38, D39, D43, D6, D76 | D47, D51–D54, D56, D58–D60 `[I]`; the rest `[I>V]` |
| twenty-questions.feature | 14 (incl. an outline of 3) | D61–D65 | D64, D65 `[I]` |
| hot-seat.feature | 11 (incl. an outline of 4) | D66–D68 | D67, D68 `[I]` |
| wordle.feature | 11 | D69–D71 | D70, D71 `[I]` |
| pausing.feature | 5 | D72, D73 | D73 `[I]` |
| host-character.feature | 8 (incl. an outline of 3) | D74, D75, D77 | all `[I>V]`; binding needs a fake talk model in test mode that does not exist (`brain/__main__.py` `_test` has no talk) |
| operator-dashboard.feature | 7 | D78–D81 | all `[I>V]` |

## RULINGS

- Suppressed by recorded ruling: 2 — the fence's "Declined": the checklist sweep (D22) and the adversarial pass (D23), both 2026-10-18 `[V]`. They suppress every checklist-category finding (usability, reliability, security, …) *as contract gaps*; the security findings of the runtime review are therefore reported as code findings on the next branch, not as scope findings here. Unconditioned: neither names a resight condition, so they can go stale silently.
- Acknowledged (accepted debt): 5 — D33 cut order (fence "Deferred"), D44 welcome extras, D82 character extras, D83 product fixes, D84 the Wordle grid (the last three added by this branch, 2026-10-18).
- Divergence — deferral whose condition is moot: D33 defers Wavelength, the banter model and Imposter "if the build runs short"; all three are built and bound (manifest: imposter.feature 4 passed, wavelength.feature 6 passed; `brain/banter.py`, `brain/talk.py`), and the fence entry stands unrevised (`features/OUT-OF-SCOPE.md` "Deferred", first entry). Remedy: a reaffirming or closing entry.
- Divergence — ruling landed elsewhere: D29 and D31 reversed in `docs/BUILD-PLAN.md` on 2026-10-18 00:15; recorded in the docket by this branch only (D45, D46).
- Self-sanctioned: 0 — no `<tool>: allow -- <reason>` markers in the bindings.
- Steering sightings: 0 — no text in the corpus addressed to the auditor. The binding comment at `test/steps/hosting.steps.ts` L52–54 ("a full circle is a sweep of the whole range, one way") is a *reinterpretation of a ruling inside a binding*, which never credits: the D5 finding stands at full rank, and the grammar that would credit it is an amending docket entry (proposed on the next branch).

## NEEDS-WORK  (ranked: severity × centrality; centrality from the ledger)

 1. one ruling clears 46: Rex reads D45–D84 and N2, N3 and ratifies or vetoes each (`<id> 2026-10-xx [V] ratifies D47` …); until then `npm run docket:strict` is red by design and every one of the 78 has-contract units rests on an unratified ruling                                   [ruling]
 2. D45 `rewrite`: Linus (the `[V]` of D29) or Rex ratifies the three-box shape, or reverses it                                                                                                                [ruling]
 3. D5 "a full circle" versus the −90..90 sweep: amend D5 (the robot's head stops at ±90 and the host sits at the edge of the circle) or fix the binding to fail; today the binding is the only thing holding the sentence to the code         [ruling → churn]
 4. D14/D42 versus `hotseat.judge` and `twenty.answer`: rule whether a model may decide an elimination or a yes/no about the secret, then code to the ruling (`brain/games/hotseat.py` `judge()`, `brain/games/twenty.py` `_answer()`)                                                                                                        [ruling → churn]
 5. D33 deferral stands while all three deferred items are built: close or reaffirm the fence entry                                           [ruling]
 6. D30/D41 fixed lines never recorded: record them (`scripts/make-voice.py`, needs the key) or amend the ruling to "Piper, ElevenLabs live when a key is there"                                                                                 [ruling → churn]
 7. host-character.feature cannot be bound without a test seam for the talk model: add `--talk fake` in test mode or re-scope the file to unit tests                                                                [churn]
 8. The unruled outcomes the bound games already take — no-majority vote, count give-up after three tries, "okay" accepting the count, Mafia at four seats, a draw at ten rounds, Wavelength's zero after eight listens, Imposter's tie outcome — each needs a ruling or a scenario (proposed on the next branch)                                     [ruling]
 9. mafia.feature D19 scenarios: "the game is over" binds to a state field; bind it to the far side (no host line after "Good game, everyone.") so probe m fails                                                             [churn]
10. The reviewer-written feature files describe the code: Rex should read them as a *contract* and strike anything he did not mean (the lines are the build's, not his)                                              [ruling]
11. gt dark: `gt refresh --root .` by the owner so the next audit has a change picture                                                       [churn]

acknowledged and self-sanctioned: none demoted beyond the five acknowledged deferrals above.
