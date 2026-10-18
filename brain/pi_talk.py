"""Talk on the QNX referee, with a one-minute circuit breaker and Mac fallback.

All imports are standard library, including net (imported here so deploy discovers
it even though Talk imports it lazily). No settings or dialogue are written here.
"""
from __future__ import annotations

import time
from typing import Any

from brain import net, settings
from brain.banter import Recap
from brain.talk import Talk

RETRY = 60.0


class PiTalk(Talk):
    def __init__(self, **kwargs: Any) -> None:
        self.unavailable_until = 0.0
        super().__init__(**kwargs)

    def active(self) -> bool:
        return time.monotonic() >= self.unavailable_until and super().active()

    def _call(self, system: str, prompt: str, **kwargs: Any) -> tuple[str | None, str | None, int]:
        # Includes write-ahead threads: repeated greetings cannot bypass the backoff.
        if not self.active():
            return None, "Pi talk unavailable", 0
        result = super()._call(system, prompt, **kwargs)
        if result[1] is not None:
            self.unavailable_until = time.monotonic() + RETRY
        return result


class PiTable:
    """Keep all Table operations remote except the optional local model calls."""
    def __init__(self, remote: Any, talk: Talk | None = None) -> None:
        self.remote = remote
        self.talk = talk if talk is not None else PiTalk()
        self.recap = Recap()  # the game so far for the Pi's own quips, as the Mac's Host keeps one: RAM only

    def __getattr__(self, name: str) -> Any:
        return getattr(self.remote, name)

    def _sync(self) -> None:
        settings.apply_talk(self.remote.talk_settings())
        if self.talk.active():
            self.talk.prepare()

    def hello(self) -> dict[str, Any]:
        hello = self.remote.hello()
        settings.apply_talk(hello.get("talk_settings", {"talk": "off"}))
        if self.talk.active():
            self.talk.prepare()  # write ahead without waiting for the body worker
        return hello

    def chat(self, situation: str, heard: str = "", **facts: Any) -> str | None:
        self._sync()  # choices may change mid-game; read them at each reply
        if self.talk.active():
            try:
                line = self.talk.reply(situation, heard, facts)
                if line:
                    return line
            except Exception:
                if isinstance(self.talk, PiTalk):
                    self.talk.unavailable_until = time.monotonic() + RETRY
        return self.remote.chat(situation, heard, **facts)

    def quip(self, slot: str, **context: Any) -> None:
        self._sync()
        if self.talk.active():
            try:
                line = self.recap.keep(slot, self.talk.quip(slot, context, self.recap))
                if line:
                    self.remote.say(line)
                    return
            except Exception:
                if isinstance(self.talk, PiTalk):
                    self.talk.unavailable_until = time.monotonic() + RETRY
        self.remote.quip(slot, **context)

    def mood(self, name: str) -> None:
        if name == "idle":
            self.recap.clear()  # every game ends on the idle look, so its recap goes with it
        self.remote.mood(name)

    def close(self) -> None:
        self.remote.close()
        net.client.close()
