// imposter.feature (D20, D101): the word dealt through the private screen, one clue
// each in seat order, a vote (won, or tied), the reveal.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  CLUE, CLUES, IMPOSTER_VOTE, brain, deal, dealtTo, defineHear, definePlaying, expectAskedInTurn, expectDealtAlone, expectFacing,
  headAt, heard, named, next, numberFrom, player, seatsFrom, start, state, text, vote, voteOut, when, word, type World,
} from './common.ts'

const CLUE_WORDS = ['sand', 'waves', 'summer', 'towel', 'shells', 'sun', 'surf', 'tide', 'boardwalk']

/** The clue turns: each player called gives a word, until the host calls the vote. */
async function clues(w: World): Promise<void> {
  const b = brain(w)
  w.asks = []
  await next(w, CLUES)
  for (;;) {
    const i = await next(w, new RegExp(`${CLUE.source}|^${IMPOSTER_VOTE.replace(/[?.]/g, '\\$&')}$`), 30)
    const line = (await b.said())[i]!
    if (line === IMPOSTER_VOTE) {
      w.cluesEnd = i
      return
    }
    const seat = numberFrom(CLUE.exec(line)![1])
    w.asks.push({ seat, yaw: await headAt(w, i) })
    await b.hear(CLUE_WORDS[w.asks.length - 1] ?? 'water')
  }
}

function expectSaw(w: World, seat: number, card: string): void {
  const d = dealtTo(w, seat)
  expectDealtAlone(w, d)
  expect(d.seen?.text, `what ${player(seat)} saw`).toBe(card)
}

export const imposter: Definer<World> = (reg) => {
  definePlaying(reg)
  defineHear(reg)

  reg.define(/^the word is "(.+)" and Player (\w+) is the Imposter$/, (w, word, who) => {
    w.rig = { word: text(word), imposter: numberFrom(who) }
  })

  reg.define(/^words are dealt through the private screen$/, async (w) => {
    when(w)
    await start(w)
    await deal(w)
  })

  reg.define(/^Players ([\w, ]+?) each saw "(.+)" alone$/, (w, who, card) => {
    for (const seat of seatsFrom(who)) expectSaw(w, seat, text(card))
  })

  reg.define(/^Player (\w+) saw "(.+)" alone$/, (w, who, card) => {
    expectSaw(w, numberFrom(who), text(card))
  })

  reg.define(/^words have been dealt$/, async (w) => {
    await start(w)
    await deal(w)
  })

  reg.define(/^the host turns to each player in seat order and asks for one word$/, async (w) => {
    when(w)
    await clues(w)
    for (const a of w.asks ?? []) expectFacing(w, a.yaw, a.seat, `asking ${player(a.seat)} for a word`)
  })

  reg.define(/^the players hear the host address Player ([\w, ]+?), each once$/, async (w, who) => {
    const said = await heard(w)
    const turns = said.slice(0, (w.cluesEnd ?? 0) - (w.since ?? 0))
    expect(turns.flatMap(named), 'the players the host addressed, in order').toEqual(seatsFrom(who))
    expect((w.asks ?? []).map((a) => a.seat), 'the players asked for a word').toEqual(seatsFrom(who))
  })

  reg.define(/^clues have been given$/, async (w) => {
    await start(w)
    await deal(w)
    await clues(w)
  })

  reg.define(/^a vote eliminates Player (\w+)$/, async (w, who) => {
    when(w)
    await voteOut(w, numberFrom(who))
  })

  reg.define(/^a vote ties between Players (\w+) and (\w+)$/, async (w, a, b) => {
    // In turn, the first four voters name the two seats alternately; the rest say nothing.
    when(w)
    const named = [numberFrom(a), numberFrom(b)]
    const { living } = await state(w)
    const asks = await vote(w, (voter) => {
      const i = living.indexOf(voter)
      return i < 4 ? word(named[i % 2]!) : undefined
    })
    expectAskedInTurn(w, asks, living)
    expect((await brain(w).said())[w.cursor ?? 0], 'the vote').toMatch(/It's a tie\. Nobody leaves\.$/)
  })
}
