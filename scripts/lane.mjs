// The two test lanes (BUILD-PLAN.md, "Two lanes"). Each lane is a list of
// commands run in order; the first failure stops the lane with its exit code.
// Every step and the lane's total are timed and printed.
//
//   fast (npm run test:fast): every agent inside a phase. oxlint, the one
//        typecheck, the Python unit tests, and the feature files named in
//        FEATURES (all of them when unset), with the wip register applied.
//   full (npm test): the gate. The strict feature-file lint, oxlint, the one
//        typecheck, the Python unit tests, every Vitest project (the harness
//        integration tests and all of features/). FEATURES is ignored here.
import { spawnSync } from 'node:child_process'
import { python } from './py.mjs'

const pytest = ['pytest', python(), ['-m', 'pytest', '-q']]
const LANES = {
  fast: [
    ['oxlint', 'npx', ['oxlint', '--deny-warnings']],
    ['typecheck', 'npm', ['run', '--silent', 'typecheck']],
    pytest,
    ['vitest features', 'npx', ['vitest', 'run', '--project', 'features']],
  ],
  full: [
    ['lint:features', 'npm', ['run', '--silent', 'lint:features']],
    ['oxlint', 'npx', ['oxlint', '--deny-warnings']],
    ['typecheck', 'npm', ['run', '--silent', 'typecheck']],
    pytest,
    ['vitest (every project)', 'npx', ['vitest', 'run']],
  ],
}

const [lane, ...rest] = process.argv.slice(2)
const steps = LANES[lane]
if (!steps || rest.length > 0) {
  console.error(`usage: node scripts/lane.mjs <${Object.keys(LANES).join('|')}>`)
  process.exit(2)
}

const env = { ...process.env }
if (lane === 'full') delete env.FEATURES
if (lane === 'fast' && env.FEATURES) console.log(`[${lane}] FEATURES=${env.FEATURES}`)

const seconds = (start) => ((performance.now() - start) / 1000).toFixed(1)
const laneStart = performance.now()
const timings = []
for (const [label, cmd, args] of steps) {
  const start = performance.now()
  console.log(`\n[${lane}] ${label}: ${cmd} ${args.join(' ')}`)
  const { status } = spawnSync(cmd, args, { stdio: 'inherit', env })
  timings.push(`${label} ${seconds(start)}s`)
  if (status !== 0) {
    console.error(`\n[${lane}] FAILED at ${label} (exit ${status}) after ${seconds(laneStart)}s`)
    process.exit(status ?? 1)
  }
}
console.log(`\n[${lane}] passed in ${seconds(laneStart)}s (${timings.join(', ')})`)
