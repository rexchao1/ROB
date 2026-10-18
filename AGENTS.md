# ROB

We are building quickly. Keep checks proportional and do not slow the work down with process.

## Reviews

- Do not use review agents or subagents to review code. No multi-agent reviews, no `/code-review` passes, no review workflows.
- A big review is only for a big-scope change: a new subsystem, a rework that touches many modules, or a change to how the parts talk to each other. Even then, do it yourself in one pass.
- Everything else finishes after you read your own diff and run the focused test for what changed, if there is one.
- Skip `/verify` unless the user asks for it.

## Starting ROB

When the user wants to test or run ROB, run `npm run restart` (about 15 s; with no terminal attached it answers its own questions) and pass on its last line, `rob: next: ...`, which says what the user has to do now. `npm run status` ends with the same line. Do not read the README or the logs first; the next line already covers the robot being off, the Mac on the wrong Wi-Fi, and the Wi-Fi having changed since start.

Only the user can power the robot or the Pi, and `scripts/wifi.sh game` needs their Mac password, so hand those steps over. Moving the Mac onto `gamemaster` cuts its internet (and this session) unless the iPhone is plugged in by USB.

## Plans

- Work that spans sessions has a plan in `docs/*-PLAN.md`. Read `docs/CONTROL-PLAN.md` before touching how ROB takes commands (stop, pause, sleep, interrupting him), the welcome, Wavelength or the head count.
