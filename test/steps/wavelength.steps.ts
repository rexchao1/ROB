// wavelength.feature (D21, D95, D100, D103): the psychic alone sees the target, a clue,
// a spoken guess scored by distance, no guess scoring zero, three rounds with the
// psychic rotating from the first round's.
//
// "Player two is the psychic this round" is the first round, the one the deal and the
// guesses are about. "Player five was the psychic in the first round and the spectrum
// is cold - hot" (D103) rigs the first round so; the two rounds after it are rigged
// with other spectra.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  NO_GUESS, POINTS, TALK, brain, cap, deal, defineHear, defineLeanIn, definePlaying, defineSomeoneSays, expectDealtAlone, heard,
  listensBetween, next, numberFrom, player, says, screenFor, seatCount, seatsFrom, start, state, text, until, when, word,
  type World,
} from './common.ts'

const OTHER_SPECTRA = ['quiet - loud', 'soft - hard', 'old - new', 'bad - good'] // brain/lines.py SPECTRA
const OTHER_TARGETS = [3, 8, 5, 2]
const FIRST_TARGET = 7 // D103: what Player five sees in the first round

/** The first round as the Background gives it (its psychic, spectrum and target), then rounds with other spectra. */
function rig(w: World, rounds: number): void {
  const psychic = w.firstPsychic ?? w.psychic
  const target = w.target ?? FIRST_TARGET
  if (psychic === undefined || w.spectrum === undefined) throw new Error('the Background names the psychic and the spectrum')
  w.rig = {
    psychic,
    rounds: [
      { spectrum: w.spectrum, target },
      ...OTHER_SPECTRA.slice(0, rounds - 1).map((spectrum, i) => ({ spectrum, target: OTHER_TARGETS[i]! })),
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

  reg.define(/^Player (\w+) was the psychic in the first round and the spectrum is "(.+)"$/, (w, who, spectrum) => {
    w.firstPsychic = numberFrom(who)
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

  // --- D95, D100: reading the guess ---------------------------------------------------------

  reg.define(/^someone answers "([^"]+)"$/, async (w, said) => {
    when(w)
    await says(w, text(said))
  })

  reg.define(/^the players hear the host say "(.+)" before any points$/, async (w, line) => {
    const since = await heard(w)
    const ask = since.indexOf(text(line))
    expect(since, `"${text(line)}"`).toContain(text(line))
    const points = since.findIndex((l) => POINTS.test(l))
    if (points >= 0) expect(points, `a points line ("${since[points]}") before the ask`).toBeGreaterThan(ask)
  })

  reg.define(/^nobody says a number for (\w+) listens$/, async (w, listens) => {
    when(w)
    const n = numberFrom(listens)
    const b = brain(w)
    const talk = (w.cursor ?? 1) - 1 // "Everyone else, talk it over..."
    expect((await b.said())[talk], 'the talk').toBe(TALK)
    // The clock runs, nobody saying anything, until the host has listened n times since the talk began.
    await until(w, `${n} listens`, async () => (await listensBetween(w, talk, Infinity)) >= n, 90)
    const zero = (await b.said()).indexOf(NO_GUESS, talk)
    if (zero >= 0) expect(await listensBetween(w, talk, zero), 'listens before the round scored zero').toBe(n)
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
    // The first round is the one the Background describes.
    const first = w.dealt![0]!
    expect(first.seat, 'the first round\'s psychic').toBe(w.firstPsychic ?? w.psychic)
    expect(first.seen, 'what the first round\'s psychic saw').toEqual({ text: String(w.target ?? FIRST_TARGET), sub: w.spectrum })
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
