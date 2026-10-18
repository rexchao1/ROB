#!/bin/sh
# Double-click to start ROB (scripts/rob.sh, docs/STARTUP-PLAN.md). The window can be
# closed once it says ROB is running; npm run stop stops it.
cd "$(dirname "$0")" && scripts/rob.sh start
