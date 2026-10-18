// What every feature's bindings share: the table, the clock, and the players' side
// of the hosting rules.
//
// The table: the friends a Background seats around the host, at known bearings,
// each seated facing the host, head down, or leaning in to the screen, pushed to
// the fake's camera as the synthetic table (the fake renders it wherever the head
// faces). The clock: the brain's virtual clock, moved in small steps until the host
// says what a step waits for, so nothing waits real time and a host that never says
// it fails the step after a bounded stretch of game time. The drivers play the
// players: leaning in when the host calls a seat, heads down at night, whispers,
// votes and clues when asked.
//
// Every claim is read back from the far side: the lines the robot played (said()),
// where its head was when it said them and what its screen showed (the fake's
// record), and the game state only where the feature text names it.
import { expect } from 'vitest'
import type { Registry } from 'gherkin-node-test/vitest'
import { getBrain, type Brain, type Screen, type TableFace } from '../harness/brain.ts'

export type Game = 'mafia' | 'imposter' | 'wavelength'

/** One lean-in the deal driver answered. */
export interface Dealt {
  seat: number
  /** The head's yaw when the host called the seat. */
  yaw: number
  /** The screen as the player leaned in, and after they leaned back. */
  before: Screen
  after: Screen
  /** The first card the screen showed while this player, alone, was close; null if none. */
  seen: Screen['showing']
}

/** One "Player N, who?" (or clue call) and where the head was when the host said it. */
export interface Ask {
  seat: number
  yaw: number
}

export interface World {
  brain?: Brain
  /** Seat N sits at bearings[N - 1]. */
  bearings?: number[]
  /** Heads at night; a seat not named is facing the host. */
  heads?: Record<number, 'frontal' | 'down'>
  game?: Game
  rig?: Record<string, unknown>
  started?: boolean
  /** Lines before this index of said() have been accounted for by a driver. */
  cursor?: number
  /** The cursor when the scenario's first When began: what the Then steps hear. */
  since?: number
  /** said().length a moment before a timed When's mark: a line due at the mark must not be in it. */
  notBefore?: number
  dealt?: Dealt[]
  asks?: Ask[]
  /** The living players when the current vote began. */
  livingAtVote?: number[]
  /** Wavelength: this round's guesser and secret number, as the scenario gives them. */
  guesser?: number
  target?: number
  /** Wavelength: the guesser of each round played, in order. */
  guessers?: number[]
  /** Imposter: the index of the line that ended the clue turns. */
  cluesEnd?: number
  /** The game time a second face leaned in beside the first (D8). */
  crowdedAt?: number
  /** A vote's When has begun; the step that gives the answers runs it. */
  voting?: boolean
  /** Mafia: the game time the day's discussion began (within a twentieth of a second). */
  dayBegan?: number
}

export type Step<W = World> = Registry<W>

// --- numbers --------------------------------------------------------------------

const ONES = [
  'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',
  'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen',
]
const TENS: Record<string, number> = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 }

/** A step argument as text (captures are strings; a data table is not). */
export function text(arg: unknown): string {
  if (typeof arg !== 'string') throw new Error(`expected a captured string, got ${typeof arg}`)
  return arg
}

/** "seven" -> 7, "twenty-three" -> 23, "one hundred twenty" -> 120, "7" -> 7. */
export function numberFrom(arg: unknown): number {
  const words = text(arg).trim().toLowerCase()
  if (/^\d+$/.test(words)) return Number(words)
  let total = 0
  for (const word of words.split(/[\s-]+/)) {
    if (word === 'hundred') total *= 100
    else if (ONES.includes(word)) total += ONES.indexOf(word)
    else if (word in TENS) total += TENS[word]!
    else if (word !== 'and') throw new Error(`not a number: ${JSON.stringify(arg)}`)
  }
  return total
}

/** 4 -> "four". */
export function word(n: number): string {
  const w = ONES[n]
  if (w === undefined) throw new Error(`no word for ${n} here`)
  return w
}

/** "one, two, four and five" or "one, then two, three" -> [1, 2, 4, 5]. */
export function seatsFrom(arg: unknown): number[] {
  return text(arg)
    .split(/\s*,\s*(?:then\s+)?|\s+and\s+/)
    .filter(Boolean)
    .map(numberFrom)
}

export function player(n: number): string {
  return `Player ${word(n)}`
}

// --- the host's lines the drivers wait on (brain/lines.py, as the players hear them) ---

export const HEADS_DOWN = 'Everyone, heads down.'
export const MAFIA_WHISPER = 'Mafia, whisper your target.'
export const MAFIA_DOWN = 'Mafia, heads back down.'
export const DOCTOR_WHISPER = 'Doctor, whisper who you save.'
export const DOCTOR_DOWN = 'Doctor, head back down.'
export const MORNING = "Everyone, heads up. It's morning."
export const EARLY_VOTE = "Okay, let's vote."
export const CLUES = "One word each, in seat order. Don't make it too easy."
export const IMPOSTER_VOTE = "Who's the Imposter? Let's vote."
export const LEAN_IN = /^Player ([a-z]+), lean in\.$/
export const WHO = /^Player ([a-z]+), who\?$/
export const CLUE = /^Player ([a-z]+), one word\.$/
export const COUNT = /^(?:[A-Z][a-z]+ of you\.|Just one of you\.|I don't see anyone yet\.)/
export const DISCUSSION = /^You have .+\. Talk it out\.$/
/** The line a vote ends on: the tally (alone, or in a tie or no-majority line), or nobody voted. */
export const VOTE_END = /^(?:[A-Z][a-z-]+ for Player [a-z]+[,.]|Nobody voted\.)/
/** The prompt after each night sweep. */
export const AFTER_SWEEP = new RegExp(`^(?:${[MAFIA_WHISPER, DOCTOR_WHISPER, MORNING].map(escape).join('|')})$`)
export const POINTS = /^(?:[A-Z][a-z-]* points?\.|No guess\. Zero points\.)$/
export const NAMED = new RegExp(`\\bPlayer (${ONES.slice(1, 11).join('|')})\\b`, 'g')

function escape(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** The seats a line names, in order ("Player four was killed" -> [4]). */
export function named(line: string): number[] {
  return [...line.matchAll(NAMED)].map((m) => numberFrom(m[1]))
}

// --- the world ----------------------------------------------------------------------

export function brain(w: World): Brain {
  if (!w.brain) throw new Error('no table yet: the Background seats the friends first')
  return w.brain
}

export function bearing(w: World, seat: number): number {
  const b = w.bearings?.[seat - 1]
  if (b === undefined) throw new Error(`no seat ${seat} at this table`)
  return b
}

export function seatCount(w: World): number {
  return w.bearings?.length ?? 0
}

/** The game state the host last reported. */
export interface GameState {
  game: string | null
  phase: string
  seats: number
  living: number[]
  out: number[]
  warnings: Record<string, number>
  sitting_out: number[]
  round: number
  over: boolean
  winner: string | null
  guesser?: number
  next_guesser?: number
  scores?: number[]
  total?: number
}

export async function state(w: World): Promise<GameState> {
  return (await brain(w).state()) as unknown as GameState
}

/** Start the scenario's When: the Then steps hear what the host says from here. */
export function when(w: World): void {
  w.since ??= w.cursor ?? 0
}

/** What the host has said since the scenario's first When (everything, without one). */
export async function heard(w: World): Promise<string[]> {
  return (await brain(w).said()).slice(w.since ?? 0)
}

// --- the table ----------------------------------------------------------------------

const CLOSE_BESIDE = 22 // degrees: a second face leaning in this far beside the first is seen as a second face

/**
 * Seat the friends: a fresh brain and fake (reset), `friends` faces spread over the
 * host's front, 30 degrees apart for five, everyone facing the host.
 */
export async function seat(w: World, friends: unknown, game?: Game): Promise<void> {
  const n = numberFrom(friends)
  if (n < 1 || n > 9) throw new Error(`a table of ${n} is not bound`)
  w.brain = await getBrain()
  await w.brain.reset()
  w.bearings = Array.from({ length: n }, (_, i) => (n === 1 ? 0 : -60 + (120 * i) / (n - 1)))
  w.heads = {}
  if (game) w.game = game
  await show(w)
}

/**
 * What the camera sees: every seat as it is (facing the host, or head down), except
 * the one leaning in to the screen, close and facing it, and the one leaning in beside
 * them, if any.
 */
export async function show(w: World, leaning: { seat?: number; beside?: number } = {}): Promise<void> {
  const faces: TableFace[] = (w.bearings ?? []).map((b, i) => {
    const s = i + 1
    if (s === leaning.seat) return { bearing: b, close: true }
    if (leaning.seat !== undefined && s === leaning.beside) return { bearing: bearing(w, leaning.seat) + CLOSE_BESIDE * Math.sign(s - leaning.seat), close: true }
    return { bearing: b, pose: w.heads?.[s] ?? 'frontal' }
  })
  await brain(w).table(faces)
}

/** Every head down but `up`'s. */
export async function headsDown(w: World, up: number[] = []): Promise<void> {
  w.heads = Object.fromEntries((w.bearings ?? []).map((_, i) => [i + 1, up.includes(i + 1) ? 'frontal' : 'down']))
  await show(w)
}

export async function headsUp(w: World): Promise<void> {
  w.heads = {}
  await show(w)
}

// --- the clock ------------------------------------------------------------------------

const STEP = 0.5 // seconds of game time per advance: inside every window the players answer in (whispers, votes, clues: four to six)
const DEAL_STEP = 0.25 // the private screen polls this often

/** Advance until `done`, at most `max` seconds of game time. */
export async function until(w: World, what: string, done: () => Promise<boolean>, max = 60, step = STEP): Promise<void> {
  const b = brain(w)
  const end = b.now + max
  while (!(await done())) {
    if (b.now >= end) throw new Error(`${what}: not within ${max} s of game time. The host last said: ${(await b.said()).slice(-6).join(' | ') || 'nothing'}`)
    await b.advance(step)
  }
}

function matches(line: string, match: string | RegExp): boolean {
  return typeof match === 'string' ? line === match : match.test(line)
}

/**
 * Advance until the host says a line matching `match` at or after the cursor; the
 * cursor moves past it. Returns its index in said().
 */
export async function next(w: World, match: string | RegExp, max = 60, step = STEP): Promise<number> {
  const b = brain(w)
  const from = w.cursor ?? 0
  const end = b.now + max
  for (;;) {
    const said = await b.said()
    const i = said.findIndex((line, j) => j >= from && matches(line, match))
    if (i >= 0) {
      w.cursor = i + 1
      return i
    }
    if (b.now >= end) {
      throw new Error(`waited ${max} s of game time for the host to say ${String(match)}; it said: ${said.slice(from).slice(-8).join(' | ') || 'nothing'}`)
    }
    await b.advance(step)
  }
}

/** Someone at the table says `words`; the clock runs until the host answers with a line. */
export async function says(w: World, words: string, max = 30): Promise<void> {
  const b = brain(w)
  const before = (await b.said()).length
  await b.hear(words)
  await until(w, `an answer to "${words}"`, async () => (await b.said()).length > before, max)
}

/** The accepted calls, as the fake recorded them, with each line's index in said(). */
async function record(w: World): Promise<{ tool: string; yaw: number; line: number }[]> {
  let yaw = 0
  let line = -1
  return (await brain(w).calls())
    .filter((c) => c.error === null)
    .map((c) => {
      if (c.tool === 'move_head') yaw = c.args.yaw as number
      if (c.tool === 'pcm') line++
      return { tool: c.tool, yaw, line }
    })
}

/** Where the head faced when the host said line `index` of said(). */
export async function headAt(w: World, index: number): Promise<number> {
  const call = (await record(w)).find((c) => c.tool === 'pcm' && c.line === index)
  if (!call) throw new Error(`the host has not said line ${index}`)
  return call.yaw
}

/** The yaw of every photo taken after line `from` and before line `to`. */
export async function photosBetween(w: World, from: number, to: number): Promise<number[]> {
  return (await record(w)).filter((c) => c.tool === 'take_photo' && c.line >= from && c.line < to).map((c) => c.yaw)
}

/** The head faced this seat (within the tolerance a seat is told apart by). */
export function expectFacing(w: World, yaw: number, seat: number, what: string): void {
  expect(Math.abs(yaw - bearing(w, seat)), `${what}: the head at ${yaw}, ${player(seat)} at ${bearing(w, seat)}`).toBeLessThanOrEqual(10)
}

// --- the game ---------------------------------------------------------------------------

/** Someone names the game; the host counts, says the count, and (nobody disputing it) starts. */
export async function start(w: World): Promise<void> {
  const b = brain(w)
  const game = w.game
  if (!game) throw new Error('no game named for this table')
  if (w.rig) await b.rig(game, w.rig)
  await b.hear(`let's play ${game}`)
  await next(w, COUNT)
  await until(w, `the host to start ${game}`, async () => (await state(w)).game === game, 30)
  w.started = true
}

/**
 * Answer every "Player N, lean in." while the deal lasts: Player N leans in alone
 * (the only close face), reads the screen, leans back. Each answer is kept in
 * w.dealt. Stops when the host calls `stopAt` (the call left for the next step) or
 * the deal is over.
 */
export async function deal(w: World, opts: { stopAt?: number } = {}): Promise<void> {
  const b = brain(w)
  w.dealt ??= []
  const end = b.now + 180
  for (;;) {
    const said = await b.said()
    const from = w.cursor ?? 0
    const i = said.findIndex((line, j) => j >= from && LEAN_IN.test(line))
    if (i >= 0) {
      const seat = numberFrom(LEAN_IN.exec(said[i]!)![1])
      if (seat === opts.stopAt) {
        w.cursor = i
        return
      }
      w.cursor = i + 1
      w.dealt.push(await leanIn(w, seat, i))
      continue
    }
    if ((await state(w)).phase !== 'deal') return
    if (b.now >= end) throw new Error(`the deal did not finish within 180 s of game time; the host last said: ${said.slice(-6).join(' | ')}`)
    await b.advance(DEAL_STEP)
  }
}

const READ = 2.0 // seconds a player stays leaned in: the card is read after 1.5

async function leanIn(w: World, seat: number, called: number): Promise<Dealt> {
  const b = brain(w)
  const yaw = await headAt(w, called)
  const before = await b.screen()
  await show(w, { seat })
  let seen: Screen['showing'] = null
  for (let t = 0; t < READ; t += DEAL_STEP) {
    await b.advance(DEAL_STEP)
    seen ??= (await b.screen()).showing
  }
  await show(w)
  await b.advance(2 * DEAL_STEP)
  return { seat, yaw, before, after: await b.screen(), seen }
}

/** Each deal answer was a player alone at the screen, called with the head on them, the card shown only while they leaned in. */
export function expectDealtAlone(w: World, d: Dealt): void {
  expectFacing(w, d.yaw, d.seat, `calling ${player(d.seat)} to lean in`)
  expect(d.before.showing, `the screen before ${player(d.seat)} leaned in`).toBeNull()
  expect(d.seen, `what ${player(d.seat)} saw leaning in`).not.toBeNull()
  expect(d.after.showing, `the screen after ${player(d.seat)} leaned back`).toBeNull()
}

export function dealtTo(w: World, seat: number): Dealt {
  const d = w.dealt?.find((x) => x.seat === seat)
  if (!d) throw new Error(`${player(seat)} was never called to lean in; the host called ${(w.dealt ?? []).map((x) => x.seat).join(', ') || 'nobody'}`)
  return d
}

/** A night: heads down (but `up`'s), the Mafia's and the Doctor's whispers (silence when not given), on to the morning. */
export async function night(w: World, opts: { mafia?: string; doctor?: string; up?: number[] } = {}): Promise<number> {
  await next(w, HEADS_DOWN)
  await headsDown(w, opts.up)
  await next(w, MAFIA_WHISPER)
  if (opts.mafia !== undefined) await brain(w).hear(opts.mafia)
  await next(w, MAFIA_DOWN)
  await next(w, DOCTOR_WHISPER)
  if (opts.doctor !== undefined) await brain(w).hear(opts.doctor)
  await next(w, DOCTOR_DOWN)
  const morning = await next(w, MORNING)
  await headsUp(w)
  return morning
}

/** The day begins; the group, done talking, says "let's vote". */
export async function day(w: World): Promise<void> {
  await next(w, DISCUSSION)
  await brain(w).hear("let's vote")
  await next(w, EARLY_VOTE)
}

/**
 * Answer each "Player N, who?" with `answer(N)` (silence for undefined) until the
 * host says how the vote came out. Returns every ask in order, with where the head
 * was; the cursor is left on the outcome line.
 */
export async function vote(w: World, answer: (seat: number) => string | undefined): Promise<Ask[]> {
  const b = brain(w)
  const asks: Ask[] = []
  w.livingAtVote ??= (await state(w)).living
  const end = b.now + 180
  let i = w.cursor ?? 0
  for (;;) {
    const said = await b.said()
    for (; i < said.length; i++) {
      const line = said[i]!
      if (VOTE_END.test(line)) {
        w.cursor = i
        w.asks = asks
        return asks
      }
      const m = WHO.exec(line)
      if (m) {
        const seat = numberFrom(m[1])
        asks.push({ seat, yaw: await headAt(w, i) })
        const a = answer(seat)
        if (a !== undefined) await b.hear(a)
      }
    }
    w.cursor = i
    if (b.now >= end) throw new Error(`the vote did not end within 180 s of game time; the host last said: ${said.slice(-6).join(' | ')}`)
    await b.advance(STEP)
  }
}

/** The host turned to each living player not sitting out, in seat order, and asked each once. */
export function expectAskedInTurn(w: World, asks: Ask[], voters: number[]): void {
  expect(asks.map((a) => a.seat), 'the players asked "who?", in order').toEqual(voters)
  for (const a of asks) expectFacing(w, a.yaw, a.seat, `asking ${player(a.seat)} "who?"`)
}

/** Votes that settle nothing: each voter names the next living seat round the table, one vote apiece. */
export function scatter(living: number[]): (voter: number) => string | undefined {
  return (voter) => {
    const i = living.indexOf(voter)
    return i < 0 ? undefined : word(living[(i + 1) % living.length]!)
  }
}

/** Through whatever comes first (the deal, a quiet night, the day's talk) to the vote. */
export async function toVote(w: World): Promise<void> {
  // A vote just ended: its reveal card is still up (the phase still "vote") until the game moves on.
  if ((await state(w)).phase === 'vote' && VOTE_END.test((await brain(w).said())[w.cursor ?? 0] ?? '')) {
    await until(w, 'the last vote to be over', async () => (await state(w)).phase !== 'vote', 10)
  }
  if ((await state(w)).phase === 'deal') await deal(w)
  if ((await state(w)).phase === 'night') await night(w)
  if ((await state(w)).phase === 'day') await day(w)
  w.livingAtVote = undefined
}

/** A vote everyone else wins for `seat` (who names the lowest other living seat). */
export async function voteOut(w: World, seat: number): Promise<Ask[]> {
  await toVote(w)
  const { living, sitting_out } = await state(w)
  const other = living.find((s) => s !== seat)
  if (!living.includes(seat) || other === undefined) throw new Error(`${player(seat)} cannot be voted out of ${living.join(', ')}`)
  const asks = await vote(w, (voter) => word(voter === seat ? other : seat))
  expectAskedInTurn(w, asks, living.filter((s) => !sitting_out.includes(s)))
  return asks
}

// --- steps more than one feature reads -----------------------------------------------------

/** A game's Background: the friends seated, the game named (it starts when a step needs it). */
export function definePlaying(reg: Step): void {
  reg.define(/^(\w+) friends are playing (Mafia|Imposter|Wavelength) with the host in the middle$/, async (w, friends, game) => {
    await seat(w, friends, text(game).toLowerCase() as Game)
  })
}

export function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function defineHear(reg: Step): void {
  reg.define(/^the players hear the host say "(.+)"$/, async (w, line) => {
    expect(await heard(w)).toContain(text(line))
    if (w.notBefore !== undefined) {
      expect((await brain(w).said()).slice(w.since ?? 0, w.notBefore), 'said before its time').not.toContain(text(line))
    }
  })
}

/** A reveal: the card on the host's screen while it says a line, then its face again. */
export function defineReveal(reg: Step): void {
  reg.define(/^the host's screen shows "(.+)" and "(.+)" while it says "(.+)"$/, async (w, big, sub, line) => {
    const b = brain(w)
    await until(w, `the host saying "${text(line)}"`, async () => (await heard(w)).includes(text(line)), 30)
    const said = await b.said()
    const i = said.lastIndexOf(text(line))
    const call = (await b.gateway.told('pcm'))[i]
    expect(call?.showing, `the screen while the host said "${text(line)}"`).toMatchObject({ text: text(big), sub: text(sub) })
  })
  reg.define(/^the host's own face is back on its screen afterwards$/, async (w) => {
    const b = brain(w)
    await until(w, "the host's face back on its screen", async () => {
      const screen = await b.screen()
      return screen.face === 'idle' && screen.showing === null
    }, 10)
  })
}

export function defineSomeoneSays(reg: Step): void {
  reg.define(/^someone says "(.+)"$/, async (w, words) => {
    when(w)
    await says(w, text(words))
  })
}

/** The lean-in: the host turns to a seat and calls it, then that player alone leans in. */
export function defineLeanIn(reg: Step): void {
  reg.define(/^the host turns to Player (\w+) and says "(.+)"$/, async (w, who, line) => {
    when(w)
    if (!w.started) await start(w)
    const seat = numberFrom(who)
    const i = await next(w, LEAN_IN)
    const said = await brain(w).said()
    expect(said[i], 'the first seat the host called').toBe(text(line))
    expect(text(line)).toBe(`${player(seat)}, lean in.`)
    expectFacing(w, await headAt(w, i), seat, `saying "${text(line)}"`)
  })
  reg.define(/^only Player (\w+)'s face is close to the host and facing it(?: again)?$/, async (w, who) => {
    await show(w, { seat: numberFrom(who) })
    await brain(w).advance(2 * DEAL_STEP)
  })
}

/** The screen as `seat` sees it: the head on them, and what it shows. */
export async function screenFor(w: World, seat: number): Promise<Screen> {
  expectFacing(w, (await brain(w).head()).yaw, seat, `${player(seat)} looking at the screen`)
  return brain(w).screen()
}
