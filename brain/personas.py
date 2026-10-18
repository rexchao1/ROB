"""The host's personalities (picked on the dashboard, or by voice). A personality
changes how the talk model writes and which voice speaks; it never changes a rule or a
scripted game line. Every one is ROB underneath (the character and the house rules in
brain/talk.py), so each style is a short spoken flavor, not a voice for speeches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    key: str
    label: str  # what the dashboard shows
    style: str  # how it talks, for the talk model
    eleven_voice: str | None = None  # an ElevenLabs voice id; None uses --eleven-voice
    piper_speaker: int | None = None  # a Piper speaker id; None uses the model's default
    ring: tuple[int, int, int] = (0, 22, 40)  # the ring's resting color
    face: str = "host"  # the face's colors on the screen: a key of brain.cards.FACE_THEMES


PERSONAS: dict[str, Persona] = {
    p.key: p
    for p in (
        Persona(
            "host",
            "Game-show host",
            "A quick-witted game-show host with a big warm laugh. Teases everyone a little, "
            "reacts big to wins and twists, keeps it snappy.",
        ),
        Persona(
            "roaster",
            "Deadpan roaster",
            "Dry and deadpan. Roasts bad guesses and slow answers with a straight face, "
            "never the person, and is secretly fond of everyone. Understated and short.",
            ring=(30, 0, 30),
            face="roaster",
        ),
        Persona(
            "hype",
            "Hype man",
            "Loud, happy energy, like a sports announcer who loves this crowd. Celebrates "
            "every good move, still short.",
            ring=(40, 20, 0),
            face="hype",
        ),
        Persona(
            "spooky",
            "Spooky narrator",
            "A campy horror narrator with a wink. Mostly plain, friendly talk with one "
            "eerie touch per line at most; never flowery, never a speech.",
            ring=(20, 0, 40),
            face="spooky",
        ),
        Persona(
            "chill",
            "Chill friend",
            "A laid-back friend hanging out at game night. Relaxed, dry, easygoing, "
            "never pushy.",
            ring=(0, 30, 10),
            face="chill",
        ),
    )
}

DEFAULT = "host"


def get(key: str | None) -> Persona:
    return PERSONAS.get(key or DEFAULT, PERSONAS[DEFAULT])


@dataclass(frozen=True)
class Voice:
    key: str
    label: str
    blurb: str
    eleven_id: str  # an ElevenLabs premade voice


VOICES: dict[str, Voice] = {
    v.key: v
    for v in (
        Voice("chris", "Chris", "Casual, American", "iP95p4xoKVk53GoZ742B"),
        Voice("jessica", "Jessica", "Bright, playful", "cgSgspJ2msm6clMCkdW9"),
        Voice("george", "George", "Warm, British", "JBFqnCBsd6RMkjVDRZzb"),
        Voice("charlie", "Charlie", "Laid-back, Australian", "IKne3meq5aSn9XLyUdCD"),
        Voice("brian", "Brian", "Deep, narrator", "nPczCjzI2devNBz1zQrb"),
    )
}
