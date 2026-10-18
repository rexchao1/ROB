// wavelength.feature (D21): the psychic alone sees the target, a clue, a spoken guess
// scored by distance, three rounds with the psychic rotating.
//
// "Player two is the psychic this round" is the round each scenario is about: the
// first round for the deal and the guesses; for "three rounds have been played", the
// third, so that the psychic of the next round, which is not played, would be Player
// three. The two rounds before it are rigged with other spectra.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  POINTS, TALK, brain, cap, deal, defineHear, defineLeanIn, definePlaying, defineSomeoneSays, expectDealtAlone, next,
  numberFrom, player, screenFor, seatCount, seatsFrom, start, state, text, word, type World,
} from './common.ts'

const OTHER_SPECTRA = ['quiet - loud', 'soft - hard', 'old - new', 'bad - good'] // brain/lines.py SPECTRA
const OTHER_TARGETS = [3, 8, 5, 2]

/** The rounds before "this round" and this round, as the rig plays them. */
function rig(w: World, rounds: number): void {
  if (w.psychic === undefined || w.spectrum === undefined || w.target === undefined) throw new Error('the Background names the psychic, the spectrum and the target')
  const n = seatCount(w)
  const before = rounds - 1
  w.rig = {
    psychic: ((w.psychic - 1 - before) % n + n) % n + 1,
    rounds: [
      ...OTHER_SPECTRA.slice(0, before).map((spectrum, i) => ({ spectrum, target: OTHER_TARGETS[i]! })),
      { spectrum: w.spectrum, target: w.target },
    ],
  }
}

/** A guess that scores `score` against `target` (ten minus the distance). */
function guessFor(target: number, score: number): number {
  const d = 10 - score
  if (target - d >= 1) return target - d
  if (target + d <= 10) return target + d
  throw new Error(`no guess scores ${score} against ${target}`)
}

/** One round from the psychic's call: they lean in alone, give a clue, and the talk begins. */
async function toGuess(w: World): Promise<number> {
  const b = brain(w)
  const dealt = (w.dealt ?? []).length
  await deal(w)
  const d = w.dealt?.[dealt]
  if (!d) throw new Error('no psychic was called to lean in')
  expectDealtAlone(w, d)
  await next(w, `${player(d.seat)}, give us your clue.`)
  await b.hear('summer')
  await next(w, TALK)
  return d.seat
}

export const wavelength: Definer<World> = (reg) => {
  definePlaying(reg)
  defineHear(reg)
  defineLeanIn(reg)
  defineSomeoneSays(reg)

  reg.define(/^Player (\w+) is the psychic this round and the spectrum is "(.+)"$/, (w, who, spectrum) => {
    w.psychic = numberFrom(who)
    w.spectrum = text(spectrum)
  })

  reg.define(/^the target is (\d+) on a scale of one to ten$/, (w, target) => {
    w.target = numberFrom(target)
    rig(w, 1)
  })

  reg.define(/^Player (\w+) sees "(.+)" and "(.+)" on the host's screen$/, async (w, who, big, small) => {
    expect((await screenFor(w, numberFrom(who))).showing).toEqual({ text: text(big), sub: text(small) })
  })

  reg.define(/^Player (\w+) has given a clue$/, async (w, who) => {
    await start(w)
    expect(await toGuess(w), 'the psychic').toBe(numberFrom(who))
  })

  reg.define(/^(\w+) rounds have been played scoring ([\w, ]+)$/, async (w, rounds, scoring) => {
    const n = numberFrom(rounds)
    const scores = seatsFrom(scoring)
    if (scores.length !== n) throw new Error(`${n} rounds, ${scores.length} scores`)
    rig(w, n)
    await start(w)
    const b = brain(w)
    for (const score of scores) {
      const psychic = await toGuess(w)
      // The group guesses from where the psychic's card put the target.
      const target = numberFrom(w.dealt!.at(-1)!.seen?.text)
      await b.hear(word(guessFor(target, score)))
      const i = await next(w, POINTS, 60)
      expect((await b.said())[i], `the score of ${player(psychic)}'s round`).toBe(`${cap(word(score))} points.`)
    }
    // This round, the last, is the one the Background describes.
    const last = w.dealt!.at(-1)!
    expect(last.seat, 'this round\'s psychic').toBe(w.psychic)
    expect(last.seen, 'what this round\'s psychic saw').toEqual({ text: String(w.target), sub: w.spectrum })
  })

  reg.define(/^the psychic for the next round would be Player (\w+)$/, async (w, who) => {
    const n = seatCount(w)
    const psychics = (w.dealt ?? []).map((d) => d.seat)
    for (let i = 1; i < psychics.length; i++) {
      expect(psychics[i], `the psychic of round ${i + 1}, after ${player(psychics[i - 1]!)}`).toBe((psychics[i - 1]! % n) + 1)
    }
    expect((await state(w)).next_psychic, 'the next round\'s psychic').toBe(numberFrom(who))
  })
}
