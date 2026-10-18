// wavelength.feature (D21, D117): everyone but the guesser sees the number, the guesser
// gives each of them a category, then says the number, scored by distance; three
// rounds with the guesser rotating.
//
// "Player two is the guesser this round" is the round each scenario is about: the
// first round, except for "three rounds have been played", where it is the third, so
// that the guesser of the next round, which is not played, would be Player three. The
// rounds before it are rigged with other numbers.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  POINTS, brain, cap, deal, defineHear, defineSomeoneSays, definePlaying, expectDealtAlone, next,
  numberFrom, player, seatCount, seatsFrom, state, start, text, word, type World,
} from './common.ts'

const OTHER_TARGETS = [3, 8, 5, 2]
const ASK = /^Player ([a-z]+), give Player ([a-z]+) a category\.$/

/** The rounds before "this round" and this round, as the rig plays them. */
function rig(w: World, rounds: number): void {
  if (w.guesser === undefined || w.target === undefined) throw new Error('the scenario names the guesser and the number')
  const n = seatCount(w)
  const before = rounds - 1
  w.rig = {
    guesser: ((w.guesser - 1 - before) % n + n) % n + 1,
    rounds: [...OTHER_TARGETS.slice(0, before).map((target) => ({ target })), { target: w.target }],
  }
}

/** A guess that scores `score` against `target` (ten minus the distance). */
function guessFor(target: number, score: number): number {
  const d = 10 - score
  if (target - d >= 1) return target - d
  if (target + d <= 10) return target + d
  throw new Error(`no guess scores ${score} against ${target}`)
}

/** One round from its deal to the guesser's "what's the number?": every category and answer given. */
async function toGuess(w: World): Promise<number> {
  const b = brain(w)
  await next(w, /^Player [a-z]+, you're guessing this round\./)
  await deal(w)
  for (;;) {
    const i = await next(w, new RegExp(`${ASK.source}|^Player [a-z]+, what's the number\\?$`))
    const line = (await b.said())[i]!
    const ask = ASK.exec(line)
    if (!ask) return numberFrom(/^Player ([a-z]+),/.exec(line)![1])
    await b.hear('animals')
    await next(w, `${player(numberFrom(ask[2]))}, name something that fits the number.`)
    await b.hear('a horse')
  }
}

export const wavelength: Definer<World> = (reg) => {
  definePlaying(reg)
  defineHear(reg)
  defineSomeoneSays(reg)

  reg.define(/^Player (\w+) is the guesser this round and the number is (\d+)$/, (w, who, target) => {
    w.guesser = numberFrom(who)
    w.target = numberFrom(target)
    rig(w, 1)
  })

  reg.define(/^the round's number is dealt$/, async (w) => {
    await start(w)
    await deal(w)
    await next(w, ASK)
    await next(w, / name something that fits the number\.$/) // the first player's turn, after the guesser's category
  })

  reg.define(/^Players ([\w, ]+) each saw "(.+)" and "(.+)" alone on the host's screen$/, (w, who, big, small) => {
    const seats = seatsFrom(who)
    expect((w.dealt ?? []).map((d) => d.seat), 'the players called to lean in, in order').toEqual(seats)
    for (const d of w.dealt ?? []) {
      expectDealtAlone(w, d)
      expect(d.seen, `what ${player(d.seat)} saw`).toEqual({ text: text(big), sub: text(small) })
    }
  })

  reg.define(/^Player (\w+) was not called to lean in$/, (w, who) => {
    expect((w.dealt ?? []).map((d) => d.seat)).not.toContain(numberFrom(who))
  })

  reg.define(/^every player has named something for Player (\w+)$/, async (w, who) => {
    await start(w)
    expect(await toGuess(w), 'the guesser').toBe(numberFrom(who))
  })

  reg.define(/^(\w+) rounds have been played scoring ([\w, ]+)$/, async (w, rounds, scoring) => {
    const n = numberFrom(rounds)
    const scores = seatsFrom(scoring)
    if (scores.length !== n) throw new Error(`${n} rounds, ${scores.length} scores`)
    rig(w, n)
    await start(w)
    const b = brain(w)
    const targets = [...OTHER_TARGETS.slice(0, n - 1), w.target!]
    const guessers: number[] = []
    for (const [r, score] of scores.entries()) {
      guessers.push(await toGuess(w))
      await b.hear(word(guessFor(targets[r]!, score)))
      const i = await next(w, POINTS, 60)
      expect((await b.said())[i], `the score of round ${r + 1}`).toBe(`${cap(word(score))} points.`)
    }
    expect(guessers.at(-1), 'this round\'s guesser').toBe(w.guesser)
    w.guessers = guessers
    await next(w, /^[A-Z][a-z-]* points?\. \S/, 60) // the total, after the last number's reveal
  })

  reg.define(/^the guesser for the next round would be Player (\w+)$/, async (w, who) => {
    const n = seatCount(w)
    const guessers = w.guessers ?? []
    for (let i = 1; i < guessers.length; i++) {
      expect(guessers[i], `the guesser of round ${i + 1}`).toBe((guessers[i - 1]! % n) + 1)
    }
    expect((await state(w)).next_guesser, 'the next round\'s guesser').toBe(numberFrom(who))
  })
}
