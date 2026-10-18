# ROB

We are building quickly. Keep checks proportional and do not slow the work down with process.

## Reviews

- Do not use review agents or subagents to review code. No multi-agent reviews, no `/code-review` passes, no review workflows.
- A big review is only for a big-scope change: a new subsystem, a rework that touches many modules, or a change to how the parts talk to each other. Even then, do it yourself in one pass.
- Everything else finishes after you read your own diff and run the focused test for what changed, if there is one.
- Skip `/verify` unless the user asks for it.
