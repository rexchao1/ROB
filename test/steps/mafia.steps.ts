// mafia.feature: the deal (D15), the night (D16, D17), the timed day and the reveal
// (D18), the win check (D19). The Background rigs the roles; everything else is
// played out at the table.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  DISCUSSION, DOCTOR_DOWN, DOCTOR_WHISPER, HEADS_DOWN, MAFIA_WHISPER, MORNING, brain, day, deal, dealtTo, defineHear, definePlaying, expectDealtAlone,
  headsDown, headsUp, next, night, numberFrom, player, scatter, seatsFrom, start, state, text, until, vote, voteOut,
  when, type World,
} from './common.ts'

const FINE = 0.05 // seconds per advance while finding the moment the day began

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
  defineHear(reg)

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
    const b = brain(w)
    const seconds = numberFrom(elapsed)
    const begun = w.dayBegan
    if (begun === undefined) throw new Error('the day has not begun')
    when(w)
    // The line due at the mark is not said a moment before it, and is said by just after.
    await b.advance(Math.max(0, begun + seconds - 2 * FINE - b.now))
    w.notBefore = (await b.said()).length
    await b.advance(Math.max(0, begun + seconds + FINE - b.now))
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
  })
}
