import { copyFileSync, mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { afterAll } from 'vitest'
import { runFeatures, type Definer, type WipEntry } from 'gherkin-node-test/vitest'
import { closeBrain } from './harness/brain.ts'
import type { World } from './steps/common.ts'
import { hosting } from './steps/hosting.steps.ts'
import { imposter } from './steps/imposter.steps.ts'
import { mafia } from './steps/mafia.steps.ts'
import { wavelength } from './steps/wavelength.steps.ts'

// gherkin-node-test over features/. One definer per feature file joins here as
// its phase binds it (test/steps/<feature>.steps.ts), driving the worker's one
// brain and mock body (test/harness/brain.ts), stopped after the run.
//
// FEATURES (fast lane only) names the feature files to run, by basename or
// path, separated by commas or spaces; unset runs them all. The full lane
// unsets it. GM_MANIFEST=1 (npm run manifest) writes run-manifest.ndjson, and
// only on an unfiltered run, because a partial account is not an account.

const ROOT = resolve(import.meta.dirname, '..')
const FEATURE_DIR = join(ROOT, 'features')

// The wip register: features (or scenarios) not yet bound. It only shrinks.
// The four signed features are bound. The seven below were written by the review
// of 2026-10-18 from the code built in workstreams W and X and the pause work
// (DOCKET.md D45 onward); they describe what was built and bind nothing yet.
const WIP: WipEntry[] = [
  'welcome', 'twenty-questions', 'hot-seat', 'wordle', 'pausing', 'host-character', 'operator-dashboard',
  // Review R's proposals (DOCKET.md D85 onward): scenarios in the bound features that
  // would change the code, held open until the rulings are ratified and abdd/3-src binds them.
  { feature: 'hosting', scenarios: [
    'The host counts the table and numbers the seats', // D96: "sweep the whole table" replaces "turn a full circle"
    'A disagreement without a number gets a second sweep', 'After three disagreements the host gives up',
    'A count below the host\'s gets a second sweep', 'Each game has a smallest table',
    'A vote that names two seats is asked for again', 'Me too is not a vote',
    'A top seat short of a majority eliminates nobody', 'Players sitting out do not count toward the majority',
  ] },
  { feature: 'mafia', scenarios: [
    'A sentence that mentions starting over is talk, not a reset', 'Restart the round starts the night again',
    'The group may vote early by saying so', 'A sentence about not being ready does not end the day',
    'Ten rounds without a win is a draw', 'The Doctor is asked every night, dead or alive',
  ] },
  { feature: 'wavelength', scenarios: [
    'A guess is read from a short answer', 'A number inside a longer sentence is talk', 'No guess the host can read scores zero',
    'The psychic rotates and the total is announced after three rounds', // D103: "Player five was the psychic in the first round" replaces the rigged reading
  ] },
  { feature: 'imposter', scenarios: ['A tied vote lets the Imposter survive'] },
]

const definers: Record<string, Definer<World>> = { hosting, imposter, mafia, wavelength }

const all = readdirSync(FEATURE_DIR).filter((f) => f.endsWith('.feature')).map((f) => basename(f, '.feature'))
const requested = (process.env.FEATURES ?? '')
  .split(/[\s,]+/)
  .filter(Boolean)
  .map((f) => basename(f, '.feature'))
for (const name of requested) {
  if (!all.includes(name)) throw new Error(`FEATURES names ${name}, which is not a feature file in features/`)
}

const filtered = requested.length > 0
if (process.env.GM_MANIFEST === '1' && filtered) {
  throw new Error('GM_MANIFEST=1 with FEATURES set: the manifest is written only by a run over every feature file')
}

const selected = filtered ? requested : all
let dir = FEATURE_DIR
if (filtered) {
  dir = mkdtempSync(join(tmpdir(), 'gamemaster-features-'))
  for (const name of selected) copyFileSync(join(FEATURE_DIR, `${name}.feature`), join(dir, `${name}.feature`))
}

const featureOf = (entry: WipEntry) => (typeof entry === 'string' ? entry : entry.feature)
const pick = <T>(entries: Record<string, T>) =>
  Object.fromEntries(Object.entries(entries).filter(([name]) => selected.includes(name)))

afterAll(closeBrain)

const manifest = join(ROOT, 'run-manifest.ndjson')
runFeatures(dir, pick(definers), {
  wip: WIP.filter((entry) => selected.includes(featureOf(entry))),
  ...(process.env.GM_MANIFEST === '1' ? { manifest } : {}),
})
