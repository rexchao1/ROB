// Runs the project's Python with the given arguments (npm run app, fixtures,
// pytest). The interpreter: GM_PYTHON if set, else .venv/bin/python (made
// by `npm run setup:py`), else python3 on PATH (the Pi).
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

export function python() {
  if (process.env.GM_PYTHON) return process.env.GM_PYTHON
  const venv = join(resolve(import.meta.dirname, '..'), '.venv', 'bin', 'python')
  return existsSync(venv) ? venv : 'python3'
}

if (import.meta.main) {
  const { status } = spawnSync(python(), process.argv.slice(2), { stdio: 'inherit' })
  process.exit(status ?? 1)
}
