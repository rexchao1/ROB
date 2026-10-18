// hosting.feature: counting the table (D5, D6), the private screen (D7, D8), heads
// down (D9 to D11) and votes by voice (D12, D13). The Background names no game, so
// these bindings host Mafia (the first game built), rigged so the roles are known.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  AFTER_SWEEP, COUNT, DISCUSSION, DOCTOR_WHISPER, EARLY_VOTE, HEADS_DOWN, LEAN_IN, MAFIA_WHISPER, MORNING,
  brain, cap, day, deal, defineHear, defineLeanIn, defineSomeoneSays, expectAskedInTurn, heard, headsDown, headsUp, named, next,
  night, numberFrom, photosBetween, player, screenFor, seat, scatter, seatsFrom, show, start, state, text, until, vote, when,
  word, type World,
} from './common.ts'

const HFOV = 60 // degrees: the camera's field of view (brain/vision.py HFOV_DEG)
const RIG = { mafia: [1], doctor: 5 }

function roleOf(w: World, seat: number): string {
  const rig = w.rig as { mafia: number[]; doctor: number }
  return rig.mafia.includes(seat) ? 'MAFIA' : rig.doctor === seat ? 'DOCTOR' : 'VILLAGER'
}

/** A game started and dealt as far as `seat`'s call, with `seat` leaned in alone and their card up. */
async function showing(w: World, seat: number): Promise<void> {
  await start(w)
  await deal(w, { stopAt: seat })
  await next(w, LEAN_IN)
  await show(w, { seat })
  await until(w, `${player(seat)}'s card on the screen`, async () => (await brain(w).screen()).showing !== null, 2, 0.25)
}

/** On to a night's "Everyone, heads down.", with every role dealt. */
async function toNight(w: World): Promise<void> {
  await start(w)
  await deal(w)
  await next(w, HEADS_DOWN)
}

async function expectWarnings(w: World, warnings: Record<string, number>): Promise<void> {
  expect((await state(w)).warnings, 'the warnings this night').toEqual(warnings)
}

export const hosting: Definer<World> = (reg) => {
  reg.define(/^(\w+) friends are seated around a table with the host in the middle$/, async (w, friends) => {
    await seat(w, friends, 'mafia')
    w.rig = RIG
  })
  defineSomeoneSays(reg)
  defineHear(reg)
  defineLeanIn(reg)

  // --- D5, D6: the count ---------------------------------------------------------------

  reg.define(/^the players see the host turn a full circle$/, async (w) => {
    // The head turns -90..90, not all the way round (docs/BUILD-PLAN.md): a full circle
    // is a sweep of the whole range, one way, with no gap between views.
    const said = await brain(w).said()
    const count = said.findIndex((line) => COUNT.test(line))
    expect(count, 'the count line').toBeGreaterThanOrEqual(0)
    const photos = await photosBetween(w, -1, count)
    expect(photos[0], 'the first photo of the sweep').toBe(-90)
    expect(photos.at(-1), 'the last photo of the sweep').toBe(90)
    for (let i = 1; i < photos.length; i++) {
      expect(photos[i]! - photos[i - 1]!, `the turn from ${photos[i - 1]} to ${photos[i]}`).toBeGreaterThan(0)
      expect(photos[i]! - photos[i - 1]!, `the turn from ${photos[i - 1]} to ${photos[i]}`).toBeLessThan(HFOV)
    }
  })

  reg.define(/^the host has counted (\w+) faces$/, async (w, faces) => {
    const n = numberFrom(faces)
    await brain(w).hear(`let's play ${w.game}`)
    const i = await next(w, COUNT)
    expect((await brain(w).said())[i]).toMatch(new RegExp(`^${cap(word(n))} of you\\.`))
    expect((await state(w)).seats).toBe(n)
  })

  reg.define(/^no game has started$/, async (w) => {
    expect((await state(w)).game, 'the game').toBeNull()
    expect((await heard(w)).filter((line) => LEAN_IN.test(line)), 'anyone called to lean in').toEqual([])
  })

  // --- D7, D8: the private screen ----------------------------------------------------------

  reg.define(/^a game has started and Player (\w+) is owed a role$/, async (w, who) => {
    await start(w)
    await deal(w, { stopAt: numberFrom(who) })
  })

  reg.define(/^Player (\w+) sees their role on the host's screen(?: again)?$/, async (w, who) => {
    const s = numberFrom(who)
    expect((await screenFor(w, s)).showing, `what ${player(s)} sees`).toMatchObject({ text: roleOf(w, s) })
  })

  reg.define(/^the host's screen is showing Player (\w+) their role$/, async (w, who) => {
    const s = numberFrom(who)
    await showing(w, s)
    expect((await screenFor(w, s)).showing).toMatchObject({ text: roleOf(w, s) })
  })

  reg.define(/^a second face appears close beside Player (\w+)'s$/, async (w, who) => {
    when(w)
    const s = numberFrom(who)
    await show(w, { seat: s, beside: s + 1 })
    w.crowdedAt = brain(w).now
  })

  reg.define(/^within one second Player (\w+) sees a blank screen$/, async (w, who) => {
    const s = numberFrom(who)
    const b = brain(w)
    const from = w.crowdedAt ?? b.now
    let blankAfter: number | undefined
    while (b.now - from < 1) {
      await b.advance(0.25)
      if ((await screenFor(w, s)).showing === null) {
        blankAfter = b.now - from
        break
      }
    }
    expect(blankAfter, 'seconds until the screen went blank').toBeDefined()
    expect(blankAfter!).toBeLessThanOrEqual(1)
  })

  reg.define(/^the host's screen went blank because a second face appeared$/, async (w) => {
    await showing(w, 2)
    await show(w, { seat: 2, beside: 3 })
    await until(w, 'the screen to go blank', async () => (await brain(w).screen()).showing === null, 1, 0.25)
    expect(await brain(w).said()).toContain('One at a time.')
  })

  // --- D9 to D11: heads down -----------------------------------------------------------------

  reg.define(/^a night phase has begun and the host said "(.+)"$/, async (w, line) => {
    expect(text(line)).toBe(HEADS_DOWN)
    await toNight(w)
  })

  reg.define(/^Player (\w+) has their head up$/, async (w, who) => {
    await headsDown(w, [numberFrom(who)])
  })

  reg.define(/^every player has their head down$/, async (w) => {
    await headsDown(w)
  })

  reg.define(/^the host sweeps the table$/, async (w) => {
    when(w)
    const down = (w.cursor ?? 1) - 1
    const after = await next(w, AFTER_SWEEP)
    expect((await photosBetween(w, down, after)).length, 'photos of the table after heads down').toBeGreaterThan(0)
  })

  reg.define(/^Player (\w+) has one warning this night$/, async (w, who) => {
    await expectWarnings(w, { [numberFrom(who)]: 1 })
  })

  reg.define(/^the players hear no player named$/, async (w) => {
    expect((await heard(w)).filter((line) => named(line).length > 0), 'lines naming a player').toEqual([])
  })

  reg.define(/^no player has a warning this night$/, async (w) => {
    await expectWarnings(w, {})
  })

  reg.define(/^a night phase has begun and Player (\w+) has one warning this night$/, async (w, who) => {
    const s = numberFrom(who)
    // Player three is the Doctor here, so that a whisper they cannot give is heard.
    w.rig = { mafia: [1], doctor: s }
    await toNight(w)
    await headsDown(w, [s])
    await next(w, `${player(s)}, heads down means heads DOWN.`, 10)
    await expectWarnings(w, { [s]: 1 })
    await next(w, MAFIA_WHISPER, 5)
    await headsDown(w)
  })

  reg.define(/^the host finds Player (\w+)'s face up again$/, async (w, who) => {
    when(w)
    // The Mafia whisper a target while Player three looks up again; the sweep after
    // "Mafia, heads back down." finds them.
    await brain(w).hear('Player four')
    await headsDown(w, [numberFrom(who)])
    await next(w, DOCTOR_WHISPER)
  })

  reg.define(/^Player (\w+) cannot whisper or vote until the next round begins$/, async (w, who) => {
    const s = numberFrom(who)
    const b = brain(w)
    await headsDown(w)
    expect((await state(w)).sitting_out).toEqual([s])
    // The Doctor sitting out whispers a save for the Mafia's target: it has no effect.
    await b.hear('Player four')
    const morning = await next(w, MORNING)
    expect((await b.said())[morning + 1], 'the morning').toBe('Player four was killed in the night.')
    await headsUp(w)
    await day(w)
    const asks = await vote(w, scatter((await state(w)).living))
    expectAskedInTurn(w, asks, [1, 2, 5])

    // The next round: Player three is back, whispers a save that holds, and votes.
    await next(w, HEADS_DOWN)
    expect(await state(w)).toMatchObject({ round: 2, sitting_out: [], warnings: {} })
    await headsDown(w)
    await next(w, MAFIA_WHISPER)
    await b.hear('Player two')
    await next(w, DOCTOR_WHISPER)
    await b.hear('Player two')
    const second = await next(w, MORNING)
    expect((await b.said())[second + 1], 'the second morning').toBe('Nobody died last night.')
    await headsUp(w)
    await day(w)
    w.livingAtVote = undefined
    const again = await vote(w, scatter((await state(w)).living))
    expectAskedInTurn(w, again, [1, 2, 3, 5])
  })

  // --- D12, D13: votes -------------------------------------------------------------------------

  reg.define(/^a day phase vote has begun with (\w+) living players$/, async (w, living) => {
    const n = numberFrom(living)
    await start(w)
    await deal(w)
    // A night that ends with five still in (the Doctor saves the Mafia's target), or with
    // Player three killed for four.
    if (n === 5) await night(w, { mafia: 'Player two', doctor: 'Player two' })
    else if (n === 4) await night(w, { mafia: 'Player three', doctor: 'Player one' })
    else throw new Error(`a vote with ${n} living players is not bound`)
    await next(w, DISCUSSION)
    await brain(w).hear("let's vote")
    await next(w, EARLY_VOTE)
    expect((await state(w)).living).toHaveLength(n)
  })

  reg.define(/^the host turns to each living player in turn and asks "who\?"$/, async (w) => {
    when(w)
    w.voting = true
  })

  reg.define(/^Players ([\w, ]+?) say "(\w+)" and Players ([\w, ]+?) say "(\w+)"$/, async (w, first, a, second, b) => {
    const answers = new Map<number, string>()
    for (const s of seatsFrom(first)) answers.set(s, text(a))
    for (const s of seatsFrom(second)) answers.set(s, text(b))
    await answer(w, (voter) => answers.get(voter))
  })

  reg.define(/^(\w+) players say "(\w+)" and (\w+) players say "(\w+)"$/, async (w, n, a, m, b) => {
    // In turn, nobody naming themself: the first n voters who are not seat a name it,
    // then the next m who are not seat b.
    const voters = (await state(w)).living
    const answers = new Map<number, string>()
    for (const [count, said] of [[numberFrom(n), text(a)], [numberFrom(m), text(b)]] as const) {
      const pick = voters.filter((v) => !answers.has(v) && v !== numberFrom(said)).slice(0, count)
      if (pick.length < count) throw new Error(`not ${count} voters left to say "${said}"`)
      for (const v of pick) answers.set(v, said)
    }
    await answer(w, (voter) => answers.get(voter))
  })

  reg.define(/^every living player is still in$/, async (w) => {
    expect((await state(w)).living).toEqual(w.livingAtVote)
    expect((await heard(w)).filter((line) => line.endsWith("you're out.")), 'anyone voted out').toEqual([])
  })
}

/** The vote the When began: each voter answers as given, and was asked in turn. */
async function answer(w: World, answers: (voter: number) => string | undefined): Promise<void> {
  if (!w.voting) throw new Error('no vote has begun')
  const { living, sitting_out } = await state(w)
  const asks = await vote(w, answers)
  expectAskedInTurn(w, asks, living.filter((s) => !sitting_out.includes(s)))
}
