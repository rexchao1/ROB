// mafia.feature: the deal (D15), the night (D16, D17, D102), the timed day and the
// reveal (D18, D87, D88, D92), the win check (D19) and the draw (D99). The Background
// rigs the roles; everything else is played out at the table.
//
// "the players hear the host say" here is heard in order: each Then finds its line
// after the one before, with the clock running for it (a restart's "Okay, this round
// again." then "Everyone, heads down."); after a timed When ("sixty seconds have
// passed") the line must already be there, not before its mark and by just after it.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  AFTER_SWEEP, DISCUSSION, DOCTOR_DOWN, DOCTOR_WHISPER, HEADS_DOWN, MAFIA_WHISPER, MORNING, VOTE_END, brain, day, deal, dealtTo,
  definePlaying, expectDealtAlone, expectGameOver, expectHeard, headsDown, headsUp, heard, next, night, numberFrom, photosBetween,
  player, scatter, seatsFrom, start, state, text, until, vote, voteOut, when, type World,
} from './common.ts'

const FINE = 0.05 // seconds per advance while finding the moment the day began

/** Votes that tie at the top with everyone voting: two for Player three, two for Player one, one for Player two. */
const TIED: Record<number, string> = { 1: 'three', 2: 'three', 3: 'one', 4: 'one', 5: 'two' }

/** The clock to `seconds` after the day began: the line due then is not said a moment before (notBefore) and is said by just after (dueBy). */
async function passed(w: World, seconds: number): Promise<void> {
  const b = brain(w)
  const begun = w.dayBegan
  if (begun === undefined) throw new Error('the day has not begun')
  await b.advance(Math.max(0, begun + seconds - 2 * FINE - b.now))
  w.notBefore = (await b.said()).length
  await b.advance(Math.max(0, begun + seconds + FINE - b.now))
  w.dueBy = (await b.said()).length
}

/** One round nobody dies in (the Doctor saves the Mafia's target) and the vote ties; the tie line's index. */
async function tiedRound(w: World): Promise<number> {
  const morning = await night(w, { mafia: 'Player two', doctor: 'Player two' })
  expect((await brain(w).said())[morning + 1], 'the morning').toBe('Nobody died last night.')
  await day(w)
  w.livingAtVote = undefined
  await vote(w, (voter) => TIED[voter])
  const i = w.cursor ?? 0
  expect((await brain(w).said())[i], 'the vote').toMatch(/It's a tie\. Nobody leaves\.$/)
  return i
}

/** The night kills a Villager (the Doctor saves themself): the morning line after it is the killing. */
async function kill(w: World, seat: number): Promise<number> {
  const rig = w.rig as { doctor: number }
  const morning = await night(w, { mafia: player(seat), doctor: player(rig.doctor) })
  const said = await brain(w).said()
  expect(said[morning + 1], 'the morning').toBe(`${player(seat)} was killed in the night.`)
  w.cursor = morning + 2
  return morning
}

/** Out in this order: a night kill, a day vote, a night kill, and so on, from the deal. */
async function outInOrder(w: World, seats: number[]): Promise<void> {
  await start(w)
  await deal(w)
  for (const [i, seat] of seats.entries()) {
    if (i % 2 === 0) await kill(w, seat)
    else await voteOut(w, seat)
  }
  expect((await state(w)).out).toEqual(seats)
}

export const mafia: Definer<World> = (reg) => {
  definePlaying(reg)

  reg.define(/^the players hear the host say "(.+)"$/, async (w, line) => {
    if (w.dueBy === undefined) {
      const i = await next(w, text(line), 30)
      expect(i, `"${text(line)}" since the When`).toBeGreaterThanOrEqual(w.since ?? 0)
      if (text(line) === HEADS_DOWN) {
        // A night begins: the players put their heads down and the host sweeps the table.
        await headsDown(w)
        const after = await next(w, AFTER_SWEEP)
        expect((await photosBetween(w, i, after)).length, 'photos of the table after heads down').toBeGreaterThan(0)
      }
    }
    await expectHeard(w, text(line))
  })

  reg.define(/^Player (\w+) is the Mafia and Player (\w+) is the Doctor$/, (w, m, d) => {
    w.rig = { mafia: [numberFrom(m)], doctor: numberFrom(d) }
  })

  // --- D15 ---------------------------------------------------------------------------------

  reg.define(/^roles are dealt$/, async (w) => {
    when(w)
    await start(w)
    await deal(w)
  })

  reg.define(/^each player in seat order has leaned in and seen their role alone$/, (w) => {
    expect((w.dealt ?? []).map((d) => d.seat), 'the seats called to lean in, in order').toEqual([1, 2, 3, 4, 5])
    for (const d of w.dealt ?? []) expectDealtAlone(w, d)
  })

  reg.define(/^Player (\w+) saw "(\w+)", Player (\w+) saw "(\w+)", and Players ([\w, ]+?) saw "(\w+)"$/, (w, a, ra, b, rb, rest, rr) => {
    const want: [number, string][] = [[numberFrom(a), text(ra)], [numberFrom(b), text(rb)], ...seatsFrom(rest).map((s): [number, string] => [s, text(rr)])]
    for (const [seat, role] of want) expect(dealtTo(w, seat).seen?.text, `what ${player(seat)} saw`).toBe(role)
  })

  // --- D16, D17 --------------------------------------------------------------------------------

  reg.define(/^it is night and every head is down$/, async (w) => {
    await start(w)
    await deal(w)
    await next(w, HEADS_DOWN)
    await headsDown(w)
  })

  reg.define(/^the host says "(.+)" and Player (\w+) quietly says "(.+)"$/, async (w, line, who, words) => {
    when(w)
    const rig = w.rig as { mafia: number[]; doctor: number }
    const role = text(line) === MAFIA_WHISPER ? rig.mafia : text(line) === DOCTOR_WHISPER ? [rig.doctor] : []
    expect(role, `${text(line)}: who answers`).toContain(numberFrom(who))
    await next(w, text(line))
    await brain(w).hear(text(words))
  })

  reg.define(/^at morning the players hear the host say "(.+)"$/, async (w, line) => {
    const morning = await next(w, MORNING)
    await headsUp(w)
    expect((await brain(w).said())[morning + 1], 'the first thing said at morning').toBe(text(line))
  })

  reg.define(/^Player (\w+) is out for the rest of the game$/, async (w, who) => {
    const seat = numberFrom(who)
    expect((await state(w)).out).toEqual([seat])
    // Through the day: not asked to vote, and still out after it.
    await day(w)
    const { living } = await state(w)
    expect(living).not.toContain(seat)
    const asks = await vote(w, scatter(living))
    expect(asks.map((a) => a.seat)).not.toContain(seat)
    await next(w, HEADS_DOWN)
    expect((await state(w)).out).toEqual([seat])
  })

  reg.define(/^every player is still in$/, async (w) => {
    expect(await state(w)).toMatchObject({ living: [1, 2, 3, 4, 5], out: [] })
  })

  // --- D18 ----------------------------------------------------------------------------------------

  reg.define(/^it is morning and the day phase has begun$/, async (w) => {
    const b = brain(w)
    await start(w)
    await deal(w)
    // Nobody dies (the Doctor saves the Mafia's target).
    await next(w, HEADS_DOWN)
    await headsDown(w)
    await next(w, MAFIA_WHISPER)
    await b.hear('Player two')
    await next(w, DOCTOR_WHISPER)
    await b.hear('Player two')
    await next(w, DOCTOR_DOWN)
    // The day's first line comes the moment it is morning: its clock starts within FINE before now.
    await next(w, DISCUSSION, 30, FINE)
    w.dayBegan = b.now
    await headsUp(w)
    expect((await state(w)).phase).toBe('day')
  })

  reg.define(/^(.+) seconds have passed$/, async (w, elapsed) => {
    when(w)
    await passed(w, numberFrom(elapsed))
  })

  // --- D87, D88, D92: what is said during the day ---------------------------------------------

  reg.define(/^someone says "([^"]+)"$/, async (w, words) => {
    when(w)
    w.notBefore = (await brain(w).said()).length
    await brain(w).hear(text(words))
  })

  reg.define(/^(.+) seconds have passed and someone says "([^"]+)"$/, async (w, elapsed, words) => {
    const b = brain(w)
    const begun = w.dayBegan
    if (begun === undefined) throw new Error('the day has not begun')
    when(w)
    await b.advance(Math.max(0, begun + numberFrom(elapsed) - b.now))
    w.notBefore = (await b.said()).length
    await b.hear(text(words))
  })

  reg.define(/^the game goes on and the players hear the host say "(.+)" (.+) seconds after the day began$/, async (w, line, elapsed) => {
    await passed(w, numberFrom(elapsed))
    const since = await heard(w)
    const i = since.indexOf(text(line))
    expect(since, `"${text(line)}"`).toContain(text(line))
    expect(since.slice(0, i), 'what the host said between the words and the mark').toEqual([])
    await expectHeard(w, text(line))
  })

  // --- D99: the draw ---------------------------------------------------------------------------

  reg.define(/^(\w+) rounds have passed with nobody killed and every vote tied$/, async (w, rounds) => {
    const n = numberFrom(rounds)
    await start(w)
    await deal(w)
    for (let i = 0; i < n; i++) await tiedRound(w)
    const said = await brain(w).said()
    expect(said.filter((l) => l === 'Nobody died last night.'), 'the mornings').toHaveLength(n)
    expect(said.filter((l) => VOTE_END.test(l)), 'the votes').toHaveLength(n)
  })

  reg.define(/^the tenth day's vote ties$/, async (w) => {
    when(w)
    expect((await brain(w).said()).filter((l) => DISCUSSION.test(l)), 'the days so far').toHaveLength(9)
    await tiedRound(w)
  })

  reg.define(/^the game is over with no winner$/, async (w) => {
    expect(await state(w), 'the game').toMatchObject({ over: true, winner: null })
    await expectGameOver(w)
  })

  // --- D102: the whispers every night -----------------------------------------------------------

  reg.define(/^Player (\w+) was killed in the first night$/, async (w, who) => {
    const seat = numberFrom(who)
    await start(w)
    await deal(w)
    // The Mafia name the seat; the Doctor (the seat itself, here) saves someone else.
    const morning = await night(w, { mafia: player(seat), doctor: player(seat === 2 ? 3 : 2) })
    expect((await brain(w).said())[morning + 1], 'the first morning').toBe(`${player(seat)} was killed in the night.`)
    // Through the first day: a vote that settles nothing.
    await day(w)
    await vote(w, scatter((await state(w)).living))
  })

  reg.define(/^the second night comes and nobody whispers$/, async (w) => {
    when(w)
    await next(w, HEADS_DOWN)
    expect((await brain(w).said()).filter((l) => l === HEADS_DOWN), 'the nights so far').toHaveLength(2)
    await headsDown(w)
    await next(w, MAFIA_WHISPER)
  })

  reg.define(/^a day phase vote eliminated Player (\w+)$/, async (w, who) => {
    await start(w)
    await deal(w)
    await voteOut(w, numberFrom(who))
  })

  // --- D19 -----------------------------------------------------------------------------------------

  reg.define(/^Players (\w+) and (\w+) are out and Player (\w+) is the only Mafia$/, async (w, a, b, m) => {
    await outInOrder(w, [numberFrom(a), numberFrom(b)])
    expect((w.rig as { mafia: number[] }).mafia).toEqual([numberFrom(m)])
    expect((await state(w)).living).toContain(numberFrom(m))
  })

  reg.define(/^a day phase vote eliminates Player (\w+)$/, async (w, who) => {
    when(w)
    await voteOut(w, numberFrom(who))
  })

  reg.define(/^Players ([\w, ]+?) are out and Players (\w+) and (\w+) remain$/, async (w, out, a, b) => {
    await outInOrder(w, seatsFrom(out))
    expect((await state(w)).living).toEqual([numberFrom(a), numberFrom(b)])
  })

  reg.define(/^the host checks the win condition$/, async (w) => {
    when(w)
    // Whatever the check finds, the game ends or the day begins.
    await until(w, 'the win check', async () => {
      const s = await state(w)
      return s.over || s.phase === 'day'
    }, 10)
  })

  reg.define(/^the game is over$/, async (w) => {
    expect((await state(w)).over, 'the game is over').toBe(true)
    await expectGameOver(w)
  })
}
