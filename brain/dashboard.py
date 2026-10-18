"""The dashboard: one page on the brain's HTTP server for running game night from the
Mac or a phone on the same network (open the server to it with --host 0.0.0.0).

  GET  /dashboard            the page (self-contained: no outside assets)
  GET  /dashboard/state      {"robot", "settings", "personas", "games", "talks",
                              "voices", "state", "feed"}; the page polls it each second
  POST /dashboard/settings   {"persona"?, "talk"?, "talk_model"?, "voice"?}; an unknown
                              name or value is a 400
  POST /dashboard/command    {"say": "let's play wordle"} | {"game": "wordle"} |
                              {"action": "reset" | "stop"}: heard at the host's next
                              listen, as if someone said it

It never shows or takes an API key: the keys stay in .env.local, and talk_model takes a
model name only.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from brain import games, personas, settings

TALKS = ("anthropic", "gemini", "ollama", "off")
VOICES = ("piper", "eleven")
LABELS = {
    "mafia": "Mafia",
    "imposter": "Imposter",
    "wavelength": "Wavelength",
    "twenty": "20 Questions",
    "hotseat": "Hot Seat",
    "wordle": "Wordle",
}
SPOKEN = {"twenty": "twenty questions", "hotseat": "hot seat"}  # what "let's play ..." says
ACTIONS = {"reset": "reset", "stop": "stop the game"}
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,63}")
_KEYLIKE = ("sk-", "aiza", "xi-")  # an API key pasted into the model box is refused


class Html(str):
    """A page, not JSON: the server sends it as text/html."""


def handle(host: Any, method: str, path: str, body: bytes) -> tuple[int, Any]:
    route = (method, path.rstrip("/") or "/")
    if route == ("GET", "/dashboard"):
        return 200, Html(PAGE)
    if route == ("GET", "/dashboard/state"):
        return 200, state(host)
    try:
        if route == ("POST", "/dashboard/settings"):
            return 200, change(_object(body))
        if route == ("POST", "/dashboard/command"):
            return 200, command(host, _object(body))
    except ValueError as e:
        return 400, {"error": str(e)}
    return 404, {"error": f"no {method} {path}"}


def state(host: Any) -> dict[str, Any]:
    with host._lock:  # noqa: SLF001 - the dashboard is the host's own page
        game = dict(host.state) if host.state is not None else {"game": None}
        feed = list(getattr(host, "feed", ()))
    return {
        "robot": getattr(host, "robot_ok", None),
        "settings": settings.snapshot(),
        "personas": [{"key": p.key, "label": p.label} for p in personas.PERSONAS.values()],
        "games": [{"key": g, "label": LABELS.get(g, g.replace("_", " ").title())} for g in games.GAMES],
        "talks": list(TALKS),
        "voices": list(VOICES),
        "eleven_voices": [{"key": v.key, "label": v.label, "blurb": v.blurb} for v in personas.VOICES.values()],
        "state": game,
        "feed": feed,
    }


def change(body: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for name, value in body.items():
        if name == "persona":
            if value not in personas.PERSONAS:
                raise ValueError(f"no personality {value!r}")
        elif name == "talk":
            if value not in TALKS:
                raise ValueError(f"talk is one of {', '.join(TALKS)}")
        elif name == "voice":
            if value not in VOICES:
                raise ValueError(f"voice is one of {', '.join(VOICES)}")
        elif name == "eleven_voice":
            if value is not None and value not in personas.VOICES:
                raise ValueError(f"no voice {value!r}")
            if os.environ.get("ELEVENLABS_API_KEY"):
                changes["voice"] = "eleven"  # picking one turns ElevenLabs on
        elif name == "talk_model":
            if value in (None, ""):
                value = None
            elif not isinstance(value, str) or not _MODEL.fullmatch(value) or value.lower().startswith(_KEYLIKE):
                raise ValueError("talk_model is a model name, like claude-haiku-5-5")
        else:
            raise ValueError(f"no setting {name!r}")
        changes[name] = value
    return settings.update(**changes)


def command(host: Any, body: dict[str, Any]) -> dict[str, Any]:
    if "say" in body:
        text = body["say"]
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise ValueError('expected {"say": "..."} under 200 characters')
    elif "game" in body:
        if body["game"] not in games.GAMES:
            raise ValueError(f"no game {body['game']!r}")
        text = "let's play " + SPOKEN.get(body["game"], body["game"])
    elif body.get("action") in ACTIONS:
        text = ACTIONS[body["action"]]
    else:
        raise ValueError('expected {"say": ...}, {"game": ...} or {"action": "reset" | "stop"}')
    host.inject(text)
    return {"ok": True, "heard": text.strip().lower()}


def _object(body: bytes) -> dict[str, Any]:
    try:
        value = json.loads(body or b"null")
    except json.JSONDecodeError as e:
        raise ValueError("body is not JSON") from e
    if not isinstance(value, dict):
        raise ValueError("body is not a JSON object")
    return value


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Game master</title>
<style>
  :root { --bg:#f5f4f0; --card:#fff; --ink:#1c1c1a; --mute:#77756e; --line:#e4e2db;
          --accent:#2457d6; --ok:#1f9d55; --bad:#d23f31; --g:#3a9a4a; --y:#d4a72c; --x:#8a8a86; }
  * { box-sizing:border-box; }
  body { margin:0; font:15px/1.4 -apple-system, system-ui, "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); }
  header { display:flex; align-items:center; gap:12px; padding:14px 18px; background:var(--card); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:1; }
  header h1 { font-size:18px; margin:0; flex:1; }
  .pill { font-size:13px; padding:4px 10px; border-radius:999px; background:#eee; color:var(--mute); white-space:nowrap; }
  .pill.ok { background:#e3f5ea; color:var(--ok); } .pill.bad { background:#fbe6e3; color:var(--bad); }
  main { display:grid; gap:14px; padding:14px; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); max-width:1100px; margin:0 auto; }
  section { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  section h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--mute); margin:0 0 10px; }
  .big { font-size:24px; font-weight:650; } .sub { color:var(--mute); }
  .row { display:flex; flex-wrap:wrap; gap:8px; }
  button { font:inherit; padding:9px 14px; border-radius:9px; border:1px solid var(--line); background:#fafaf8; color:var(--ink); cursor:pointer; }
  button:hover { border-color:#c9c6bd; }
  button.on { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.warn { color:var(--bad); }
  input[type=text] { font:inherit; padding:9px 12px; border:1px solid var(--line); border-radius:9px; flex:1; min-width:0; }
  form { display:flex; gap:8px; margin-top:10px; }
  dl { display:grid; grid-template-columns:auto 1fr; gap:4px 14px; margin:10px 0 0; }
  dt { color:var(--mute); } dd { margin:0; }
  .grid { display:grid; gap:4px; margin-top:10px; justify-content:start; }
  .grid .r { display:flex; gap:4px; }
  .grid span { width:38px; height:38px; display:flex; align-items:center; justify-content:center; font-weight:700; text-transform:uppercase; color:#fff; border-radius:5px; background:var(--x); }
  .grid span.g { background:var(--g); } .grid span.y { background:var(--y); } .grid span.e { background:#fff; border:2px solid var(--line); color:var(--ink); }
  .feed { list-style:none; margin:0; padding:0; max-height:360px; overflow:auto; }
  .feed li { padding:6px 0; border-bottom:1px solid var(--line); display:flex; gap:10px; }
  .feed time { color:var(--mute); font-variant-numeric:tabular-nums; font-size:13px; flex:none; }
  .feed b { font-weight:600; flex:none; width:44px; font-size:13px; }
  .feed .heard b { color:var(--accent); } .feed .said b { color:var(--ok); }
  .meter { height:10px; background:#eee; border-radius:6px; overflow:hidden; margin-top:8px; }
  .meter i { display:block; height:100%; background:var(--accent); }
  .hint { font-size:13px; color:var(--mute); margin-top:8px; }
</style>
</head>
<body>
<header><h1>Game master</h1><span id="robot" class="pill">robot: ?</span></header>
<main>
  <section id="now"><h2>Now</h2><div class="big" id="game">No game</div><div class="sub" id="phase"></div><dl id="facts"></dl><div id="extra"></div></section>
  <section><h2>Play</h2><div class="row" id="games"></div>
    <div class="row" style="margin-top:10px"><button data-action="reset">Reset</button><button class="warn" data-action="stop">Stop the game</button></div>
    <form id="sayform"><input type="text" id="say" placeholder="Say something to the host" autocomplete="off"><button>Say</button></form>
    <div class="hint">Typed lines are heard at the host's next listen.</div></section>
  <section><h2>Personality</h2><div class="row" id="personas"></div></section>
  <section><h2>Talk</h2><div class="row" id="talks"></div>
    <form id="modelform"><input type="text" id="model" placeholder="Model (blank for the default)" autocomplete="off"><button>Set</button></form>
    <h2 style="margin-top:16px">Voice</h2><div class="row" id="voices"></div></section>
  <section style="grid-column:1/-1"><h2>Heard and said</h2><ul class="feed" id="feed"></ul></section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const post = (path, body) => fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)})
  .then(r => r.json()).then(j => { if (j.error) alert(j.error); poll(); });
const LABEL = {anthropic:"Claude", gemini:"Gemini", ollama:"Ollama", off:"Off", piper:"Piper", eleven:"ElevenLabs"};
let gameLabels = {};

function buttons(box, items, current, onclick) {
  const key = JSON.stringify([items, current]);
  if (box.dataset.key === key) return;
  box.dataset.key = key; box.replaceChildren();
  for (const it of items) {
    const b = el("button", it.key === current ? "on" : "", it.label);
    b.onclick = () => onclick(it.key); box.appendChild(b);
  }
}
function fact(dl, k, v) { if (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length)) return; dl.append(el("dt", "", k), el("dd", "", Array.isArray(v) ? v.join(", ") : typeof v === "object" ? Object.entries(v).map(([a, b]) => a + ": " + b).join(", ") : String(v))); }
function seatList(v) { return Array.isArray(v) ? v.map(s => "Player " + s) : v; }

function board(rows) {
  const g = el("div", "grid");
  for (const row of rows) {
    let letters = "", marks = "";
    if (typeof row === "string") { [letters, marks = ""] = row.split(/[:\\s]+/); }
    else if (Array.isArray(row)) { for (const c of row) { if (Array.isArray(c)) { letters += c[0] || " "; marks += c[1] || "x"; } else if (c && typeof c === "object") { letters += c.letter || " "; marks += c.mark || c.color || "x"; } } }
    else if (row && typeof row === "object") { letters = row.word || row.guess || ""; marks = row.marks || row.colors || row.score || ""; if (Array.isArray(marks)) marks = marks.join(""); }
    const r = el("div", "r");
    for (let i = 0; i < Math.max(5, letters.length); i++) {
      const m = (marks[i] || (letters[i] ? "x" : "e")).toLowerCase()[0];
      r.appendChild(el("span", m === "g" ? "g" : m === "y" ? "y" : letters[i] ? "" : "e", letters[i] || ""));
    }
    g.appendChild(r);
  }
  return g;
}

function render(d) {
  const r = $("robot");
  r.textContent = d.robot === true ? "robot connected" : d.robot === false ? "robot not answering" : "robot: not heard from yet";
  r.className = "pill" + (d.robot === true ? " ok" : d.robot === false ? " bad" : "");
  gameLabels = Object.fromEntries(d.games.map(g => [g.key, g.label]));
  const s = d.state || {};
  $("game").textContent = s.game ? (gameLabels[s.game] || s.game) : "No game";
  $("phase").textContent = s.game ? [s.phase, s.over ? "over" : "", s.winner ? "winner: " + s.winner : ""].filter(Boolean).join(" \\u00b7 ") : "Waiting for someone to pick a game";
  const dl = $("facts"); dl.replaceChildren();
  fact(dl, "Seats", s.seats); fact(dl, "Round", s.round || undefined);
  fact(dl, "Still in", seatList(s.living)); fact(dl, "Out", seatList(s.out));
  fact(dl, "Category", s.category); fact(dl, "Seconds", s.seconds);
  fact(dl, "Questions", s.questions); fact(dl, "Left", s.left);
  fact(dl, "Scores", s.scores); fact(dl, "Total", s.total);
  const extra = $("extra"); extra.replaceChildren();
  if (typeof s.questions === "number") {
    const m = el("div", "meter"), i = el("i"); i.style.width = Math.min(100, s.questions / 20 * 100) + "%"; m.appendChild(i); extra.appendChild(m);
  }
  if (Array.isArray(s.board)) extra.appendChild(board(s.board));

  buttons($("games"), d.games, null, k => post("/dashboard/command", {game:k}));
  buttons($("personas"), d.personas, d.settings.persona, k => post("/dashboard/settings", {persona:k}));
  buttons($("talks"), d.talks.map(k => ({key:k, label:LABEL[k] || k})), d.settings.talk, k => post("/dashboard/settings", {talk:k}));
  buttons($("voices"), d.voices.map(k => ({key:k, label:LABEL[k] || k})), d.settings.voice, k => post("/dashboard/settings", {voice:k}));
  if (document.activeElement !== $("model")) $("model").value = d.settings.talk_model || "";

  const f = $("feed"), key = JSON.stringify(d.feed);
  if (f.dataset.key !== key) {
    f.dataset.key = key; f.replaceChildren();
    for (const line of [...d.feed].reverse()) {
      const li = el("li", line.kind);
      li.append(el("time", "", new Date(line.t * 1000).toLocaleTimeString()), el("b", "", line.kind), el("span", "", line.text));
      f.appendChild(li);
    }
    if (!d.feed.length) f.appendChild(el("li", "", "Nothing yet."));
  }
}

let busy = false;
function poll() {
  if (busy) return; busy = true;
  fetch("/dashboard/state").then(r => r.json()).then(render)
    .catch(() => { $("robot").textContent = "brain not answering"; $("robot").className = "pill bad"; })
    .finally(() => { busy = false; });
}
document.querySelectorAll("[data-action]").forEach(b => b.onclick = () => post("/dashboard/command", {action:b.dataset.action}));
$("sayform").onsubmit = (e) => { e.preventDefault(); const t = $("say").value.trim(); if (t) post("/dashboard/command", {say:t}); $("say").value = ""; };
$("modelform").onsubmit = (e) => { e.preventDefault(); post("/dashboard/settings", {talk_model:$("model").value.trim()}); $("model").blur(); };
poll(); setInterval(poll, 1000);
</script>
</body>
</html>
"""
