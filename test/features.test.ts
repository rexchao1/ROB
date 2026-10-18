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
// The four signed features are bound, review R's scenarios in them (DOCKET.md D87
// onward) included. The seven below were written by the review of 2026-10-18 from the
// code built in workstreams W and X and the pause work (DOCKET.md D45 onward); they
// describe what was built and bind nothing yet.
const WIP: WipEntry[] = [
  'welcome', 'twenty-questions', 'hot-seat', 'wordle', 'pausing', 'host-character', 'operator-dashboard',
  // Rex's 3ae4edc, transcribed (D109 to D112): a lean-in by voice, the speaker by voice, say that again;
  // held open until Rex ratifies them and a build binds them.
  { feature: 'hosting', scenarios: [
    'Show me puts the card up for a few seconds without a close face', 'Got it moves the deal on',
    'A lean-in nobody answers is asked again with the way round the camera',
    'The speaker moves to the Mac and back by voice', 'Say that again repeats the last line',
  ] },
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
