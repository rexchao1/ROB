"""The talk's words (brain/talk.py): fit() trims a long line instead of throwing it away,
the welcome's prompt carries the talk so far, and the greeting is written ahead. The
HTTP is stubbed: no call leaves the process."""

import pytest

from brain import settings, talk


@pytest.fixture
def anthropic(monkeypatch):
    """Settings on Anthropic's default model at low effort, a fake key, .env.local unread."""
    monkeypatch.setattr(settings, "current", settings.Settings(talk="anthropic"))
    monkeypatch.setattr(talk, "_env_loaded", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123456")


def _settled(t):
    """Every line being written ahead has finished, so no thread outlives the stub."""
    for slot in list((t._ready or {}).values()):  # noqa: SLF001
        assert slot["done"].wait(2)


def test_a_long_reply_keeps_the_sentences_that_fit_and_leaves_off_one_cut_short():
    cut = ("I am feeling mysterious and ready, and the night is young. "
           "Now, which game shall we descend into: Mafia, Imposter, Wavel")
    assert talk.fit(cut) == "I am feeling mysterious and ready, and the night is young."
    four = "Doing great. Thanks for asking. Ready when you are. Mafia, maybe?"
    assert talk.fit(four) == "Doing great. Thanks for asking. Ready when you are."
    assert talk.fit("ROB: Hey!\nGood to see you. What are we playing?") == "Hey! Good to see you. What are we playing?"


def test_a_line_is_dropped_only_when_its_first_sentence_will_not_do():
    assert talk.fit(" ".join(["word"] * (talk.MAX_WORDS + 1)) + ".") is None
    assert talk.fit("Player three looks like they know the rules. Anyway, Mafia?") is None
    assert talk.fit("Ha, nice one. Player three looks ready. Anyway, Mafia?") == "Nice one."  # the stock opener goes too
    assert talk.fit("Great question! Mafia is fun.") is None


def test_the_welcome_prompt_carries_the_talk_so_far_and_says_what_the_games_are(anthropic):
    t = talk.Talk(log=lambda msg: None)
    prompt = t._prompt("welcome", "uh, how are you?", {  # noqa: SLF001
        "answering": True, "games": "Mafia and Imposter", "suggestion": "Imposter",
        "transcript": [["ROB", "Hey, I'm ROB. What are we playing?"], ["them", "hold on"]],
    })
    assert "ROB: Hey, I'm ROB. What are we playing?\nThem: hold on" in prompt
    assert 'Just now someone said: "uh, how are you?"' in prompt
    assert "In Imposter, everyone gets the same secret word" in prompt and "Want to play it?" not in prompt
    assert "Answer what they said first" in prompt
    settings.current.persona = "dramatic"
    assert "Builds suspense and drags out every reveal" in t._system()  # noqa: SLF001


def test_a_welcome_reply_has_room_to_finish(anthropic, monkeypatch):
    sent = []

    def answer(self, url, body, headers, timeout=None):
        sent.append(body)
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "I'm great, thanks. You?"}]}

    monkeypatch.setattr(talk.Talk, "_post", answer)
    t = talk.Talk(log=lambda msg: None)
    assert t.reply("welcome", "how are you?", {}) == "I'm great, thanks. You?"
    assert sent[0]["max_tokens"] == talk.WELCOME_TOKENS


def test_the_greeting_is_written_ahead_taken_at_once_and_the_next_one_started(anthropic, monkeypatch):
    prompts, systems = [], []

    def answer(self, url, body, headers, timeout=None):
        prompts.append(body["messages"][0]["content"])
        systems.append(body["system"])
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": f"Hey, I'm ROB. Line {len(prompts)}, what are we playing?"}]}

    monkeypatch.setattr(talk.Talk, "_post", answer)
    t = talk.Talk(log=lambda msg: None)
    t.prepare()
    _settled(t)
    assert sorted(p.split(" ")[0] for p in prompts) == ["Game", "Someone"]  # the greeting and the wake-up line
    first = t.reply("welcome.greeting", "", {})
    assert first is not None and first.startswith("Hey, I'm ROB.")
    _settled(t)
    assert len(prompts) == 3  # the next greeting, for the next "reset"
    settings.current.persona = "dramatic"
    assert t.reply("welcome.greeting", "", {}) is not None
    _settled(t)
    assert "Builds suspense and drags out every reveal" in systems[-2]  # written again for the new personality
    settings.current.talk = "off"
    calls = len(prompts)
    assert t.reply("welcome.woke", "", {}) is None and len(prompts) == calls
