import { spawn, type ChildProcess } from 'node:child_process'
import { afterAll, beforeAll, describe, expect, test } from 'vitest'
import { Brain, FakeGateway, python, ROOT, TEST_TABLE_TOKEN, type Call } from '../harness/brain.ts'

// The referee as its own process, as it runs on the QNX Pi: the brain in test mode
// with --referee remote serves its Table on loopback, `python -S -m brain.referee`
// (no site-packages: the standard library only) plays through it, and the robot is
// told exactly what the brain playing alone tells it, call for call, on the same
// virtual clock. The Table takes the referee's calls only with its token (D85): the test
// brain's is fixed (TEST_TABLE_TOKEN), and a referee without it is refused and stops.

const SETUP = ['set_off_timeout', 'set_blink', 'set_avatar', 'set_all_leds', 'move_head']
const FIVE = [-60, -30, 0, 30, 60].map((bearing) => ({ bearing }))

/** Spawn and resolve once every pattern has matched the output; each match's first group. */
function waitFor(child: ChildProcess, name: string, patterns: RegExp[], timeoutMs = 15_000): Promise<string[]> {
  let output = ''
  return new Promise((ok, fail) => {
    const timer = setTimeout(() => fail(new Error(`${name} did not start within ${timeoutMs} ms:\n${output}`)), timeoutMs)
    const check = (chunk: Buffer) => {
      output = (output + chunk.toString()).slice(-20_000)
      const found = patterns.map((p) => p.exec(output)?.[1])
      if (found.every((f) => f !== undefined)) {
        clearTimeout(timer)
        ok(found as string[])
      }
    }
    child.stdout?.on('data', check)
    child.stderr?.on('data', check)
    child.on('exit', (code) => {
      clearTimeout(timer)
      fail(new Error(`${name} exited (${code}):\n${output}`))
    })
  })
}

async function post(url: string, path: string, body?: unknown): Promise<unknown> {
  const res = await fetch(url + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}) })
  if (!res.ok) throw new Error(`POST ${path} answered ${res.status}: ${await res.text()}`)
  return res.json()
}

async function get(url: string, path: string, headers: Record<string, string> = {}): Promise<unknown> {
  const res = await fetch(url + path, { headers })
  if (!res.ok) throw new Error(`GET ${path} answered ${res.status}: ${await res.text()}`)
  return res.json()
}

const BEARER = { Authorization: `Bearer ${TEST_TABLE_TOKEN}` }

/** Spawn and resolve with the exit code, or fail after timeoutMs. */
function exitCode(child: ChildProcess, timeoutMs = 15_000): Promise<{ code: number | null; output: string }> {
  let output = ''
  const keep = (chunk: Buffer) => {
    output = (output + chunk.toString()).slice(-20_000)
  }
  child.stdout?.on('data', keep)
  child.stderr?.on('data', keep)
  return new Promise((ok, fail) => {
    const timer = setTimeout(() => {
      child.kill()
      fail(new Error(`still running after ${timeoutMs} ms:\n${output}`))
    }, timeoutMs)
    child.on('exit', (code) => {
      clearTimeout(timer)
      ok({ code, output })
    })
  })
}

/** What the robot was told, without the wall times, sequence numbers and each brain's own temporary folder for card sets. */
function record(calls: Call[]): unknown[] {
  return calls.map((c) => {
    const args = typeof c.args.archive_path === 'string' ? { ...c.args, archive_path: c.args.archive_path.split('/').pop() } : c.args
    return [c.tool, args, c.error, c.line ?? null]
  })
}

/** Count the table, deal, and wait out the lean-ins: a few hundred calls. */
async function playMafia(url: string): Promise<unknown> {
  await post(url, '/test/table', { faces: FIVE })
  await post(url, '/test/rig', { mafia: { mafia: [2], doctor: 4 } })
  await post(url, '/test/hear', { text: "let's play mafia" })
  for (let i = 0; i < 2; i++) await post(url, '/test/advance', { seconds: 30 })
  return get(url, '/test/state')
}

describe('the referee as a separate process, over loopback', () => {
  let gateway: FakeGateway
  let brain: ChildProcess
  let referee: ChildProcess
  let url: string
  let tableUrl: string

  beforeAll(async () => {
    gateway = await FakeGateway.start()
    brain = spawn(python(), ['-m', 'brain', '--test', '--gateway', gateway.mcpUrl, '--port', '0', '--referee', 'remote', '--table-port', '0'], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    ;[tableUrl, url] = (await waitFor(brain, 'the brain', [/table for the referee at (http:\/\/\S+)/, /listening on (http:\/\/\S+)/])) as [string, string]
    referee = spawn(python(), ['-S', '-m', 'brain.referee', '--table', tableUrl, '--token', TEST_TABLE_TOKEN], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] })
    await waitFor(referee, 'the referee', [/(attached) to the table/])
    await post(url, '/test/reset')
  })

  afterAll(() => {
    referee?.kill()
    brain?.kill()
    gateway?.stop()
  })

  test('the table says a referee is attached, to a caller with the token only', async () => {
    expect(await get(tableUrl, '/table/attached', BEARER)).toMatchObject({ attached: true })
    expect((await fetch(tableUrl + '/table/attached')).status).toBe(401)
    expect((await fetch(tableUrl + '/table/attached', { headers: { Authorization: 'Bearer not-it' } })).status).toBe(401)
  })

  test('a referee without the token, or with another, is refused and stops with 3; the attached one plays on', async () => {
    const bare = spawn(python(), ['-S', '-m', 'brain.referee', '--table', tableUrl], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, GM_TABLE_TOKEN: '' } })
    expect((await exitCode(bare)).code).toBe(2)
    const wrong = spawn(python(), ['-S', '-m', 'brain.referee', '--table', tableUrl, '--token', 'not-it'], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] })
    const { code, output } = await exitCode(wrong)
    expect(code).toBe(3)
    expect(output).toMatch(/token/)
    expect(await get(tableUrl, '/table/attached', BEARER)).toMatchObject({ attached: true })
  })

  test('after a reset the robot is set up, then the referee idle-listens', async () => {
    await post(url, '/test/reset')
    expect((await gateway.calls()).map((c) => c.tool)).toEqual(SETUP)
    await post(url, '/test/advance', { seconds: 5 })
    expect((await gateway.calls()).map((c) => c.tool)).toEqual([...SETUP, 'set_all_leds', 'listen'])
  })

  test('a game played by the referee tells the robot what the brain alone would', async () => {
    await post(url, '/test/reset')
    const remoteState = await playMafia(url)
    const remote = record(await gateway.calls())

    const alone = await Brain.start()
    try {
      const localState = await playMafia(alone.url)
      const local = record(await alone.calls())
      expect(local.length).toBeGreaterThan(100)
      expect(remote).toEqual(local)
      expect(remoteState).toEqual(localState)
      expect(remoteState).toMatchObject({ game: 'mafia', seats: 5 })
    } finally {
      alone.stop()
    }
  })

  test('a reset mid-game drops the game: no word said, the state cleared, idle-listening again', async () => {
    await post(url, '/test/reset')
    await post(url, '/test/table', { faces: FIVE })
    await post(url, '/test/hear', { text: "let's play mafia" })
    await post(url, '/test/advance', { seconds: 15 })
    expect((await gateway.said())[0]).toMatch(/^Five of you\./)
    await post(url, '/test/reset')
    expect(await get(url, '/test/state')).toEqual({ game: null })
    await post(url, '/test/advance', { seconds: 5 })
    expect((await gateway.calls()).map((c) => c.tool)).toEqual([...SETUP, 'set_all_leds', 'listen'])
    expect(await gateway.said()).toEqual([])
  })
})
