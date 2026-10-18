"""The dashboard: one page on the brain's HTTP server for running game night from the
Mac or a phone on the same network (open the server to it with --host 0.0.0.0).

  GET  /dashboard            the page (self-contained: no outside assets), in three tabs:
                              Play, ROB (personality, voice, speaker) and AI (provider,
                              model, effort, the talk's status and a test call)
  GET  /dashboard/state      {"robot", "paused", "asleep", "settings", "personas", "games", "talks",
                              "talk_models", "efforts", "voices", "eleven_voices",
                              "speakers", "talk_status", "state", "feed"}; the page polls
                              it each second
  POST /dashboard/settings   {"persona"?, "talk"?, "talk_model"?, "effort"?, "voice"?,
                              "eleven_voice"?, "speaker"?}; an unknown name or value is a
                              400. A new talk drops a talk_model meant for another
                              provider; a new speaker applies at once (Host.set_speaker)
  POST /dashboard/talk-test  one real call to the talk now, the way the game calls it:
                              {"ok", "provider", "model", "line", "error", "ms"}
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

from brain import games, personas, settings, talk

TALKS = ("anthropic", "gemini", "ollama", "off")
VOICES = ("piper", "eleven")
SPEAKERS = {"robot": "Robot", "mac": "This Mac"}
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
_NO_TALK = {"ok": False, "provider": None, "model": None, "line": None, "error": "the talk is not set up", "ms": 0}


class Html(str):
    """A page, not JSON: the server sends it as text/html."""


def handle(host: Any, method: str, path: str, body: bytes) -> tuple[int, Any]:
    route = (method, path.rstrip("/") or "/")
    if route == ("GET", "/dashboard"):
        return 200, Html(PAGE)
    if route == ("GET", "/dashboard/state"):
        return 200, state(host)
    if route == ("POST", "/dashboard/talk-test"):  # takes seconds: this request's own thread waits
        return 200, host.talk.test() if host.talk is not None else dict(_NO_TALK)
    try:
        if route == ("POST", "/dashboard/settings"):
            return 200, change(host, _object(body))
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
        "paused": bool(getattr(host, "paused", False)),
        "asleep": bool(getattr(host, "asleep", False)),
        "settings": settings.snapshot(),
        "personas": [{"key": p.key, "label": p.label} for p in personas.PERSONAS.values()],
        "games": [{"key": g, "label": LABELS.get(g, g.replace("_", " ").title())} for g in games.GAMES],
        "talks": list(TALKS),
        "talk_models": talk.MODELS,
        "efforts": list(talk.EFFORTS),
        "voices": list(VOICES),
        "eleven_voices": [{"key": v.key, "label": v.label, "blurb": v.blurb} for v in personas.VOICES.values()],
        "speakers": [{"key": k, "label": label} for k, label in SPEAKERS.items()],
        "talk_status": host.talk.status() if host.talk is not None else None,
        "state": game,
        "feed": feed,
    }


def change(host: Any, body: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    speaker = None
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
        elif name == "effort":
            if value not in talk.EFFORTS:
                raise ValueError(f"effort is one of {', '.join(talk.EFFORTS)}")
        elif name == "speaker":
            if not isinstance(value, str) or value not in SPEAKERS:
                raise ValueError("speaker is robot or mac")
            speaker = value
            continue  # applied below, through the host, once everything else checks out
        else:
            raise ValueError(f"no setting {name!r}")
        changes[name] = value
    if "talk" in changes and "talk_model" not in changes:
        model = settings.snapshot()["talk_model"]
        if model and not _fits(changes["talk"], model):
            changes["talk_model"] = None  # the new provider's default, not a model it cannot run
    snap = settings.update(**changes)
    if speaker is not None:
        if hasattr(host, "set_speaker"):
            host.set_speaker(speaker)
        else:  # a host without set_speaker yet: the body and the saved pick by hand
            host.body.speaker = speaker
            settings.update(speaker=speaker)
        snap = settings.snapshot()
    return snap


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


def _fits(provider: str, model: str) -> bool:
    """The model is one this provider can run (the test Talk.choice makes); off keeps any."""
    if provider == "anthropic":
        return model.startswith("claude")
    if provider == "gemini":
        return model.startswith("gemini")
    if provider == "ollama":
        return not model.startswith(("claude", "gemini"))
    return True


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
  .top { background:var(--card); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:1; }
  header { display:flex; align-items:center; gap:12px; padding:14px 18px 6px; max-width:1100px; margin:0 auto; }
  header h1 { font-size:18px; margin:0; flex:1; }
  nav { display:flex; gap:2px; padding:0 8px; max-width:1100px; margin:0 auto; }
  nav button { border:0; border-bottom:2px solid transparent; border-radius:0; background:none; padding:9px 14px 10px; color:var(--mute); font-weight:600; }
  nav button:hover { color:var(--ink); }
  nav button[aria-selected=true] { color:var(--accent); border-bottom-color:var(--accent); }
  .where { max-width:1100px; margin:0 auto; padding:12px 18px 0; font-size:13px; color:var(--mute); }
  .where a { color:var(--accent); }
  .pill { font-size:13px; padding:4px 10px; border-radius:999px; background:#eee; color:var(--mute); white-space:nowrap; }
  .pill.ok { background:#e3f5ea; color:var(--ok); } .pill.bad { background:#fbe6e3; color:var(--bad); }
  .pill.warn { background:#fbf1d9; color:#8a6410; }
  main { display:grid; gap:14px; padding:14px; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); max-width:1100px; margin:0 auto; align-items:start; }
  main[hidden], [hidden] { display:none !important; }
  section { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  section.wide { grid-column:1/-1; }
  section h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--mute); margin:0 0 10px; }
  section h2.next { margin-top:18px; }
  .big { font-size:24px; font-weight:650; } .sub { color:var(--mute); }
  .row { display:flex; flex-wrap:wrap; gap:8px; }
  button { font:inherit; padding:9px 14px; border-radius:9px; border:1px solid var(--line); background:#fafaf8; color:var(--ink); cursor:pointer; text-align:left; }
  button:hover { border-color:#c9c6bd; }
  button:disabled { opacity:.6; cursor:default; }
  button.on { background:var(--accent); border-color:var(--accent); color:#fff; }
  button.warn { color:var(--bad); }
  button small { display:block; font-size:12px; color:var(--mute); margin-top:1px; }
  button.on small { color:#dce5fb; }
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
  .status { padding:10px 12px; border-radius:9px; background:#f1f0eb; color:var(--ink); }
  .status.ok { background:#e3f5ea; color:var(--ok); } .status.bad { background:#fbe6e3; color:var(--bad); }
  .said-ok { color:var(--ok); } .said-bad { color:var(--bad); }
</style>
</head>
<body>
<div class="top">
  <header><h1>Game master</h1><span id="paused" class="pill warn" hidden>paused</span><span id="asleep" class="pill" hidden>asleep: tap its head to wake it</span><span id="robot" class="pill">robot: ?</span></header>
  <nav role="tablist">
    <button role="tab" data-tab="play">Play</button>
    <button role="tab" data-tab="rob">ROB</button>
    <button role="tab" data-tab="ai">AI</button>
  </nav>
</div>
<p class="where">Keys, the camera and tuning are on the game screen: <a href="/dash">open it</a>.</p>

<main id="play" role="tabpanel">
  <section id="now"><h2>Now</h2><div class="big" id="game">No game</div><div class="sub" id="phase"></div><dl id="facts"></dl><div id="extra"></div></section>
  <section><h2>Play</h2><div class="row" id="games"></div>
    <div class="row" style="margin-top:10px"><button id="pause" data-say="pause">Pause</button><button data-say="resume">Resume</button><button data-action="reset">Reset</button><button class="warn" data-action="stop">Stop the game</button></div>
    <form id="sayform"><input type="text" id="say" placeholder="Say something to the host" autocomplete="off"><button>Say</button></form>
    <div class="hint">Typed lines are heard at the host's next listen, as if someone said them.</div></section>
  <section class="wide"><h2>Heard and said</h2><ul class="feed" id="feed"></ul></section>
</main>

<main id="rob" role="tabpanel" hidden>
  <section><h2>Personality</h2><div class="row" id="personas"></div>
    <div class="hint">How ROB talks. The rules of the games never change.</div></section>
  <section><h2>Voice</h2><div class="row" id="voices"></div>
    <h2 class="next">ElevenLabs voice</h2><div class="row" id="eleven"></div>
    <div class="hint">ElevenLabs needs ELEVENLABS_API_KEY, set on the game screen's Settings &gt; Keys. Without it ROB keeps the built-in voice.</div></section>
  <section><h2>Speaker</h2><div class="row" id="speakers"></div>
    <div class="hint">Where ROB's voice plays. You can also say "change your speaker to the Mac".</div></section>
</main>

<main id="ai" role="tabpanel" hidden>
  <section><h2>Provider</h2><div class="row" id="talks"></div>
    <div class="hint">Who writes ROB's lines. The games' rules and scores never come from the AI.</div></section>
  <section id="modelbox"><h2>Model</h2><div class="row" id="models"></div>
    <form id="modelform"><input type="text" id="model" placeholder="Custom model name" autocomplete="off"><button>Set</button></form>
    <div class="hint">For a model not listed; blank goes back to the default.</div>
    <h2 class="next">Effort</h2><div class="row" id="efforts"></div>
    <div class="hint">Low is the fastest and fine for party lines.</div></section>
  <section><h2>Status</h2><div class="status" id="status">Not tried yet</div>
    <div class="row" style="margin-top:10px"><button id="test">Test</button></div>
    <div class="hint" id="tested">Test makes one real call now, the way the game does.</div></section>
</main>

<script>
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const json = (path, body) => fetch(path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)}).then(r => r.json());
const post = (path, body) => json(path, body).then(j => { if (j.error) alert(j.error); poll(); });
const PROVIDERS = {anthropic:["Claude", "Anthropic"], gemini:["Gemini", "Google"], ollama:["Ollama", "On this Mac"], off:["Scripted", "No AI, ROB's own lines"]};
const ENGINES = {piper:["Built-in", "On this Mac, no key"], eleven:["ElevenLabs", "Live, needs a key"]};
const KEYNAME = {anthropic:"ANTHROPIC_API_KEY", gemini:"GEMINI_API_KEY"};
const TABS = ["play", "rob", "ai"];
let gameLabels = {}, last = null, gen = 0, busy = false;

function buttons(box, items, current, onclick) {
  const key = JSON.stringify([items, current]);
  if (box.dataset.key === key) return;
  box.dataset.key = key; box.replaceChildren();
  for (const it of items) {
    const on = current !== undefined && it.key === current;
    const b = el("button", on ? "on" : "", it.label);
    if (it.blurb) b.appendChild(el("small", "", it.blurb));
    if (current !== undefined) b.setAttribute("aria-pressed", String(on));
    b.onclick = () => onclick(it.key); box.appendChild(b);
  }
}
const pairs = (keys, names) => keys.map(k => ({key:k, label:(names[k] || [k])[0], blurb:(names[k] || [])[1]}));
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

// The model the talk uses: the picked one when this provider can run it (as Talk.choice), else its default.
function fits(p, m) { return p === "anthropic" ? m.startsWith("claude") : p === "gemini" ? m.startsWith("gemini") : p === "ollama" ? !/^(claude|gemini)/.test(m) : false; }
function modelLabel(d, p, m) { const it = ((d.talk_models || {})[p] || []).find(x => x.key === m); return it ? it.label : m; }

function talkStatus(d) {
  const t = d.talk_status, box = $("status");
  let text = "Not tried yet", cls = "";
  if (!t) text = "The talk is not set up in this brain, so ROB says its own lines.";
  else if (t.provider === "off") text = "Scripted: ROB says its own lines, no AI.";
  else if (t.key_set === false) { text = "No key set: add " + (KEYNAME[t.provider] || "the key") + " on the game screen's Settings > Keys."; cls = "bad"; }
  else if (t.ok === true) { text = "Working: " + modelLabel(d, t.provider, t.model) + (t.ms != null ? ", " + t.ms + " ms" : ""); cls = "ok"; }
  else if (t.ok === false) { text = "Last call failed: " + (t.error || "no answer"); cls = "bad"; }
  else text = "Not tried yet: " + modelLabel(d, t.provider, t.model) + ". Press Test, or start a game.";
  if (t && t.at && t.ok != null) text += " (at " + new Date(t.at * 1000).toLocaleTimeString() + ")";
  box.textContent = text; box.className = "status" + (cls ? " " + cls : "");
}

function render(d) {
  const r = $("robot");
  r.textContent = d.robot === true ? "robot connected" : d.robot === false ? "robot not answering" : "robot: not heard from yet";
  r.className = "pill" + (d.robot === true ? " ok" : d.robot === false ? " bad" : "");
  $("paused").hidden = !d.paused;
  $("asleep").hidden = !d.asleep;
  $("pause").className = d.paused ? "on" : "";
  gameLabels = Object.fromEntries(d.games.map(g => [g.key, g.label]));
  const s = d.state || {}, set = d.settings;
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
  buttons($("games"), d.games, undefined, k => post("/dashboard/command", {game:k}));

  buttons($("personas"), d.personas, set.persona, k => setting({persona:k}));
  buttons($("voices"), pairs(d.voices, ENGINES), set.voice, k => setting({voice:k}));
  buttons($("eleven"), [{key:null, label:"Default", blurb:"The one ROB started with"}, ...d.eleven_voices], set.eleven_voice ?? null, k => setting({eleven_voice:k}));
  buttons($("speakers"), d.speakers, set.speaker || "robot", k => setting({speaker:k}));

  const p = set.talk, models = (d.talk_models || {})[p] || [];
  buttons($("talks"), pairs(d.talks, PROVIDERS), p, k => setting({talk:k}));
  $("modelbox").hidden = p === "off";
  const picked = set.talk_model && fits(p, set.talk_model) ? set.talk_model : null;
  const model = picked || (models[0] || {}).key;
  buttons($("models"), models, model, k => setting({talk_model:k}));
  if (document.activeElement !== $("model")) $("model").value = picked && !models.some(m => m.key === picked) ? picked : "";
  buttons($("efforts"), (d.efforts || []).map(k => ({key:k, label:k[0].toUpperCase() + k.slice(1)})), set.effort || "low", k => setting({effort:k}));
  talkStatus(d);

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

// A change redraws from the settings it answers; a poll that left before it is dropped.
function setting(body) {
  gen++;
  json("/dashboard/settings", body).then(j => {
    gen++;
    if (j.error) { alert(j.error); poll(); return; }
    if (last) { last.settings = j; render(last); }
  }).catch(() => alert("The brain did not answer."));
}

function poll() {
  if (busy) return; busy = true;
  const g = gen;
  fetch("/dashboard/state").then(r => r.json()).then(d => { if (g === gen) { last = d; render(d); } })
    .catch(() => { $("robot").textContent = "brain not answering"; $("robot").className = "pill bad"; })
    .finally(() => { busy = false; });
}

function tab(name) {
  if (!TABS.includes(name)) name = "play";
  document.querySelectorAll("nav button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  TABS.forEach(t => { $(t).hidden = t !== name; });
  try { localStorage.setItem("dashboard.tab", name); } catch (e) { /* private mode: the tab is not remembered */ }
}
document.querySelectorAll("nav button").forEach(b => b.onclick = () => tab(b.dataset.tab));
let saved = null; try { saved = localStorage.getItem("dashboard.tab"); } catch (e) { /* none */ }
tab(saved);

document.querySelectorAll("[data-action]").forEach(b => b.onclick = () => post("/dashboard/command", {action:b.dataset.action}));
document.querySelectorAll("[data-say]").forEach(b => b.onclick = () => post("/dashboard/command", {say:b.dataset.say}));
$("sayform").onsubmit = (e) => { e.preventDefault(); const t = $("say").value.trim(); if (t) post("/dashboard/command", {say:t}); $("say").value = ""; };
$("modelform").onsubmit = (e) => { e.preventDefault(); setting({talk_model:$("model").value.trim()}); $("model").blur(); };
$("test").onclick = () => {
  const b = $("test"), out = $("tested");
  b.disabled = true; out.className = "hint"; out.textContent = "Asking the model...";
  json("/dashboard/talk-test", {}).then(j => {
    const who = j.model ? " (" + (last ? modelLabel(last, j.provider, j.model) : j.model) + ", " + j.ms + " ms)" : "";
    out.textContent = j.ok ? (j.line ? "It said: " + j.line : "It answered.") + who : "Failed: " + (j.error || "no answer") + who;
    out.className = "hint " + (j.ok ? "said-ok" : "said-bad");
  }).catch(() => { out.textContent = "The brain did not answer."; out.className = "hint said-bad"; })
    .finally(() => { b.disabled = false; poll(); });
};
poll(); setInterval(poll, 1000);
</script>
</body>
</html>
"""
