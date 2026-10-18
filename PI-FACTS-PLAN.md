# Pi facts and talk

Goal: ROB keeps selected group facts and public game totals on the QNX Pi, and uses
its own talk model there when connected, falling back to the Mac.

Constraints: standard library only on QNX; 30 entries of 100 characters; no dialogue,
private roles or identities on disk; write only changes; Mac facts stay in RAM;
no deployment, process restarts or push. Leave the other agents' files alone.

Done when: focused Python tests and the referee integration check pass where the
local dependencies allow, docs explain deployment, and rob/pi-facts is committed.

- [done] Add bounded facts, explicit voice commands and public game totals.
- [done] Wrap Pi talk, mirror Mac choices, add opt-in key transfer.
- [done] Document lifecycle and deployment, run focused checks, read diff, commit.


Verification so far: all 293 focused Python tests passed across the initial pass and
corrected remote/Pi-talk and host reruns. The referee integration passes all four tests.
`python3 -S -m brain.referee --help` and `sh -n qnx/deploy.sh` pass. The integration
uses the main checkout's node_modules through an ignored symlink. No Pi connection,
deploy, running-process restart, real model call or push was performed.

The only initial failures were a test using the default bind address instead of
loopback, and a startup settings call queued behind virtual-clock setup. The new
hello snapshot avoids that queue; the settings method still handles later changes.

TALK-PLAN.md was left untouched as requested. Steps 8 (dialogue lifecycle), 9 (facts)
and 10 (Pi talk) are implemented here. Step 11 (uplink) remains on the other branch.
Real QNX/internet and room testing remain for Rex after the branches are merged.
