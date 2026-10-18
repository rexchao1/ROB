// The system under test: the fake gateway (`python test/fake_gateway.py --port 0`,
// the stackchan-mcp daemon as the brain sees it) and the brain against it
// (`python -m brain --test --gateway <fake>/mcp --port 0`), spawned once per test
// worker (getBrain) and driven black-box over HTTP. Step bindings reset both
// before each scenario, set what the camera sees (the synthetic table, rendered
// wherever the head faces) and what the microphone hears through the brain's
// /test/*, advance the brain's virtual clock, and assert on the far side: what
// the fake gateway recorded the brain told the robot (calls(), said()) and what
// the robot is doing (screen(), head()). /test/state is read only for state the
// feature text itself names.
import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'

export const ROOT = resolve(import.meta.dirname, '..', '..')
const TABLE = join(ROOT, 'test', 'fixtures', 'table.py')

/** GM_PYTHON, else .venv/bin/python, else python3 (scripts/py.mjs resolves the same way). */
export function python(): string {
  if (process.env.GM_PYTHON) return process.env.GM_PYTHON
  const venv = join(ROOT, '.venv', 'bin', 'python')
  return existsSync(venv) ? venv : 'python3'
}

/** One thing the brain told the robot, as the fake gateway recorded it: a tool call, or "pcm" (a line played). */
export interface Call {
  seq: number
  tool: string
  args: Record<string, unknown>
  /** The fake's answer (a refusal's payload too); null for a schema refusal. */
  answer: unknown
  /** Why it was refused, or null. */
  error: string | null
  /** Wall seconds since the fake's last reset (the brain's game time is its own virtual clock). */
  t: number
  /** "pcm" only: the line's text, carried in the test voice's clip. */
  line?: string | null
}

/** The robot's screen: the avatar face set, blinking, and the card that face shows from the loaded set. */
export interface Screen {
  face: string
  blink: boolean
  showing: { text: string; sub: string | null } | null
  /** The loaded card set's path, or null. */
  set: string | null
}

export interface Head {
  yaw: number
  pitch: number
}

/** A face at the synthetic table (test/fixtures/table.py): bearing in degrees, 0 ahead, positive to the host's right. */
export interface TableFace {
  bearing: number
  pose?: 'frontal' | 'down'
  close?: boolean
}

/** Spawn a process and resolve with the URL from its "listening on <url>" line. */
function listen(child: ChildProcess, name: string, timeoutMs: number): Promise<{ url: string; output: () => string }> {
  let output = ''
  let listening = false
  return new Promise((ok, fail) => {
    const timer = setTimeout(() => {
      child.kill()
      fail(new Error(`${name} did not say it was listening within ${timeoutMs} ms:\n${output}`))
    }, timeoutMs)
    const keep = (chunk: Buffer) => {
      output = (output + chunk.toString()).slice(-20_000) // the host logs every line it says: keep the tail
    }
    child.stdout?.on('data', (chunk: Buffer) => {
      keep(chunk)
      const match = /listening on (http:\/\/\S+)/.exec(output)
      if (!listening && match?.[1]) {
        listening = true
        clearTimeout(timer)
        ok({ url: match[1], output: () => output })
      }
    })
    child.stderr?.on('data', keep)
    child.on('exit', (code) => {
      clearTimeout(timer)
      if (!listening) fail(new Error(`${name} exited (${code}) before listening:\n${output}`))
    })
  })
}

async function json<T>(url: string, method: 'GET' | 'POST', path: string, body?: unknown, contentType = 'application/json'): Promise<T> {
  const res = await send(url, method, path, body, contentType)
  if (!res.ok) throw new Error(`${method} ${path} answered ${res.status}: ${await res.text()}`)
  return (await res.json()) as T
}

function send(url: string, method: 'GET' | 'POST', path: string, body?: unknown, contentType = 'application/json'): Promise<Response> {
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.body = body instanceof Uint8Array ? body : JSON.stringify(body)
    init.headers = { 'Content-Type': contentType }
  }
  return fetch(url + path, init)
}

/** The fake gateway (test/fake_gateway.py): the far side every assertion reads. */
export class FakeGateway {
  readonly url: string
  private readonly child: ChildProcess

  private constructor(url: string, child: ChildProcess) {
    this.url = url
    this.child = child
  }

  static async start(timeoutMs = 15_000): Promise<FakeGateway> {
    const child = spawn(python(), [join(ROOT, 'test', 'fake_gateway.py'), '--port', '0'], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] })
    const { url } = await listen(child, 'the fake gateway', timeoutMs)
    return new FakeGateway(url, child)
  }

  /** The MCP endpoint the brain is pointed at. */
  get mcpUrl(): string {
    return this.url + '/mcp'
  }

  request(method: 'GET' | 'POST', path: string, body?: unknown, contentType?: string): Promise<Response> {
    return send(this.url, method, path, body, contentType)
  }

  /** Everything the brain told the robot since the last reset, in order, accepted or refused. */
  calls(): Promise<Call[]> {
    return json(this.url, 'GET', '/mock/calls')
  }

  /** The accepted calls of one tool (e.g. "move_head", "set_avatar", "load_avatar_set"), in order. */
  async told(tool: string): Promise<Call[]> {
    return (await this.calls()).filter((c) => c.tool === tool && c.error === null)
  }

  /** The lines the robot played, in order. */
  async said(): Promise<string[]> {
    return (await this.told('pcm')).map((c) => c.line ?? '')
  }

  /** Every yaw the head was told to turn to, in order. */
  async moves(): Promise<number[]> {
    return (await this.told('move_head')).map((c) => c.args.yaw as number)
  }

  screen(): Promise<Screen> {
    return json(this.url, 'GET', '/mock/screen')
  }

  head(): Promise<Head> {
    return json(this.url, 'GET', '/mock/head')
  }

  stop(): void {
    this.child.kill()
  }
}

/** The brain in test mode, with the fake gateway it drives. */
export class Brain {
  /** The brain's virtual clock (seconds) as of the last reset or advance. */
  now = 0
  readonly url: string
  readonly gateway: FakeGateway
  private readonly child: ChildProcess

  private constructor(url: string, gateway: FakeGateway, child: ChildProcess) {
    this.url = url
    this.gateway = gateway
    this.child = child
  }

  static async start(timeoutMs = 15_000): Promise<Brain> {
    const gateway = await FakeGateway.start(timeoutMs)
    const child = spawn(python(), ['-m', 'brain', '--test', '--gateway', gateway.mcpUrl, '--port', '0'], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] })
    try {
      const { url } = await listen(child, 'the brain', timeoutMs)
      const brain = new Brain(url, gateway, child)
      await brain.reset()
      return brain
    } catch (err) {
      gateway.stop()
      throw err
    }
  }

  request(method: 'GET' | 'POST', path: string, body?: unknown, contentType?: string): Promise<Response> {
    return send(this.url, method, path, body, contentType)
  }

  /**
   * Start over: the host stopped wherever it is, the fake gateway's record, camera,
   * microphone, head and screen cleared, the clock at zero, rigs and the table
   * forgotten, and the host started again: it sets the robot up (the record then
   * holds set_off_timeout, set_blink, set_avatar idle, set_all_leds, move_head 0)
   * and idle-listens for a game's name; with `welcome`, it starts with the welcome
   * (D38) as the real host does.
   */
  async reset(opts: { welcome?: boolean } = {}): Promise<number> {
    const body = opts.welcome ? { welcome: true } : undefined
    this.now = (await json<{ now: number }>(this.url, 'POST', '/test/reset', body)).now
    return this.now
  }

  /**
   * What the camera sees. Without pans, the synthetic table itself: the fake renders
   * it at whatever yaw the head faces, for every photo from now on. With pans, the
   * table rendered once at each (the camera serves the one nearest the head).
   */
  async table(faces: TableFace[], pans?: number[]): Promise<void> {
    if (pans === undefined) {
      await json(this.url, 'POST', '/test/table', { faces })
      return
    }
    for (const pan of pans) await this.frame(renderTable(pan, faces), pan)
  }

  /** Push a PNG or JPEG to the camera: what it sees facing `pan`, or at every angle without one. */
  async frame(png: Uint8Array, pan?: number): Promise<void> {
    const path = pan === undefined ? '/test/frame' : `/test/frame?pan=${pan}`
    await json(this.url, 'POST', path, png, 'image/png')
  }

  /** What the microphone hears: the host's next listen, wherever it is, answers this. */
  async hear(text: string): Promise<void> {
    await json(this.url, 'POST', '/test/hear', { text })
  }

  /** Move the virtual clock forward; answers once the host has done everything due by then. */
  async advance(seconds: number): Promise<number> {
    this.now = (await json<{ now: number }>(this.url, 'POST', '/test/advance', { seconds })).now
    return this.now
  }

  /** Fix the next game's random choices (brain/games/__init__.py names the keys). */
  async rig(game: 'mafia' | 'imposter' | 'wavelength', choices: Record<string, unknown>): Promise<void> {
    await json(this.url, 'POST', '/test/rig', { [game]: choices })
  }

  /** The game state the host last reported ({game: null} before any). */
  state(): Promise<Record<string, unknown>> {
    return json(this.url, 'GET', '/test/state')
  }

  calls(): Promise<Call[]> {
    return this.gateway.calls()
  }

  said(): Promise<string[]> {
    return this.gateway.said()
  }

  screen(): Promise<Screen> {
    return this.gateway.screen()
  }

  head(): Promise<Head> {
    return this.gateway.head()
  }

  moves(): Promise<number[]> {
    return this.gateway.moves()
  }

  stop(): void {
    this.child.kill()
    this.gateway.stop()
  }
}

/** One frame of the synthetic table at this pan, as PNG bytes (test/fixtures/table.py). */
export function renderTable(pan: number, faces: TableFace[]): Uint8Array {
  const args = [TABLE, `--pan=${pan}`, ...faces.map((f) => `--face=${f.bearing}:${f.pose ?? 'frontal'}${f.close ? ':close' : ''}`)]
  const out = spawnSync(python(), args, { cwd: ROOT, maxBuffer: 16 * 1024 * 1024 })
  if (out.status !== 0) throw new Error(`table.py failed (${out.status}): ${out.stderr.toString()}`)
  return new Uint8Array(out.stdout)
}

let shared: Promise<Brain> | undefined

/** The worker's one brain (and fake gateway), started on first use. */
export function getBrain(): Promise<Brain> {
  shared ??= Brain.start()
  return shared
}

/** Stop the worker's brain and fake gateway, if started (afterAll). */
export async function closeBrain(): Promise<void> {
  if (!shared) return
  const brain = await shared.catch(() => undefined)
  shared = undefined
  brain?.stop()
}
