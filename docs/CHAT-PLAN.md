# Plan: ROB is a chatbot who hosts games, not a game bot who chats

Rex, 2026-10-18. Between games ROB talks about anything, moves his head and face on his own, and changes his own settings when it fits, all chosen by the talk model through tool calls. The pull toward a game stays, but it is his judgment, not a script.

## Goal

At the table, talking to ROB feels like talking to a person: he follows any topic, remembers the last few minutes of talk, looks at whoever he is answering, nods, makes faces, switches to the spooky voice when someone asks, and gets the group into a game when the moment is right. The games themselves still play by the code's rules.

## What stays fixed

- Hard commands (stop, sleep, reset, pause, be quiet) are read by code before the model ever sees the line and act at once (`docs/CONTROL-PLAN.md`). The model never delays them.
- D14 and D42's core: rules, counts, scores, winners and secrets are the code's. The model chooses words and actions; every action is a tool the code checks before running it.
- Offline or with no key, the welcome's scripted router (`brain/games/welcome.py`, `_hear`) runs exactly as now. The feature files test that path, so they keep passing.
- The QNX referee shares `brain/lobby.py`, `brain/games/` and the talk code on the Pi: standard library only.
- Anthropic only for tools. Gemini and Ollama keep today's text-only chat.

## How it works

One heard line, one model call. The call carries the system prompt, the talk so far (both sides, in RAM), what ROB can see (the count, the suggestion, the games and what each needs) and the tools. The answer is the spoken line plus any number of tool calls in the same response, so moving costs no extra round trip. The line plays while the motions run.

Only tools that return information (count the table, the rules of a game) take a second call, and only one: the model gets the result and writes the line.

Tools, each checked in code (a bad argument is dropped and logged, never spoken):

| Tool | What it does | Check |
|---|---|---|
| `look` | turn to a seat, the speaker, or back to center | seat exists |
| `gesture` | nod, shake, tilt, a look around | from a fixed list |
| `face` | a mood (idle, tense, win, night, day) | `MOODS` |
| `count_table` | the camera sweep; returns the count | as `Welcome._count` |
| `rules` | the scripted rules of one game, said as written | game exists |
| `start_game` | start a game | the game exists; too few people goes through the game's own check |
| `setting` | personality, voice, speaker, volume | `settings.CHOICES`, the persona and voice keys, volume 0 to 100 |
| `remember`, `forget` | the facts on the Pi | `brain/facts.py` filters as now |
| `nap` | say goodnight and sleep until a tap | none |


## Steps

1. [done, D118] Rule it: a new docket entry amending D42 says a model may choose the host's actions from a fixed set of tools, each checked in code, and still decides no rule, count, score, winner or secret. Read `features/welcome.feature` and `features/host-character.feature` for scenarios this contradicts.
2. [done] Tool calls in `brain/talk.py`: `Talk.act(heard, context) -> Turn(line, actions)` builds an Anthropic request with `tools`, reads text and `tool_use` blocks, runs at most one follow-up for information tools, same timeouts and fallbacks as `reply`. `fit()` still cleans the line. Focused test with a fake HTTP answer.
3. [done] The tool set and its checker, `brain/agent.py` (standard library): the table above, each tool a small function over the `Table`, returning what it did for the log. `Table.setting` on the Host and in `remote.py`. Tests for each check.
4. [done] The lobby turn: in `Welcome._hear`, after hard commands and reset, a line that is not noise goes to `Talk.act` when the talk is active; the scripted router runs when it is not, or when the call fails. Talk memory goes from 12 lines to about 40 (RAM only, cleared as now). The chat caps (`max_chats`, `reply_gap_seconds`) go. Lines can run to about 40 words in the lobby. The nudges for a quiet table become the model's too, with the scripted nudges as fallback.
5. [done, first pass; knows the suggested game for each headcount] The prompt: any topic the table brings up, held like a conversation; a pull toward a game when the talk winds down, someone seems bored, or a few minutes have passed, never on every line; how to use the body (look at whoever he answers, a gesture now and then, not on every line); the existing house rules, minus the ones that only made sense for a scripted bot.
6. [done] Opening lines: the lines Rex picked replace the model-written greeting (recorded once, so they play instantly). The second line becomes an open question, not the games menu; the games come up in the talk.
7. [done: Mafia day talk, Twenty Questions, Wordle] Side talk during games: a line addressed to ROB that the game is not waiting for gets a reply with a smaller toolset (look, gesture, face; no games, no settings) and only the public recap (`banter.Recap`), never a secret. Only at listens that are not votes, whispers, guesses or counts, and only for a line addressed to ROB that the game cannot use.
8. [not started] Replays: `scripts/talk-replay.py` gets tool calls; run a handful of lobby conversations against the real model and tune the prompt for too many motions, too many game pushes, or too few.
9. [not started] Try it at the table.

## Done when

Steps 1 to 8 pass their focused tests (`test_talk`, `test_welcome`, `test_lobby`, `test_remote`, the new `test_agent`), the feature files still pass, and a table session shows ROB chatting off-topic, moving on his own, and starting a game the group agreed to.

## Rex's answers (2026-10-18)

1. ROB can start a game himself, but he would rather the group picks: the prompt says so, and `start_game` has no "they asked" check. Too few people still goes through the game's own check.
2. He can change his own personality, voice, speaker and volume unasked.
3. He can decide to remember something on his own; `brain/facts.py` still refuses private-sounding facts.
4. Side talk during games is built now, with the lobby: he can chat whenever.

Opening lines picked: 2, 3, 4, 5, 6, 9 from the options, each followed by one of A, B, D (step 6).

## Interface (shared by the builders)

- `Table.act(situation, heard="", **facts) -> {"line", "actions": [{"name", "args"}]} | None`: the model's turn, no side effects. On the Mac `Host.act` calls `Talk.act`; on the referee, `PiTalk` or the Mac over `remote.py`. Situation "lobby" or "game"; facts carry `tools` (the names offered), the transcript and, on a follow-up, `results`. For "game" the Host adds the public recap.
- `Table.gesture(name)` and `Table.setting(name, value) -> bool`, both in `remote.py`'s `METHODS`.
- `brain/agent.py`: `run_turn(table, situation, heard, facts, allowed) -> Outcome | None`, the tool list and the checks.

## Risks

- Speed: a tool response is about the same size as today's, but an information tool adds about a second. Counting the table already takes longer than that.
- Cost: a bigger prompt each turn (40 lines of memory plus tools). Haiku keeps it small.
- He might push games too little now. The replay set in step 8 is where that gets tuned.
