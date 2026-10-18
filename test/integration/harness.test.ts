import { afterAll, beforeAll, describe, expect, test } from 'vitest'
import { Brain, dashKey, renderTable } from '../harness/brain.ts'

// The harness smoke test: the brain spawns in test mode against the fake gateway;
// /test/* reports what the brain holds, nothing pre-seeded; what a test sets on
// the camera and the microphone reaches the brain only through the fake, and
// what the brain does to the robot is read back from the fake's record.

const SETUP = ['set_off_timeout', 'set_blink', 'set_avatar', 'set_all_leds', 'move_head']

describe('the brain in test mode against the fake gateway', () => {
  let brain: Brain
  beforeAll(async () => {
    brain = await Brain.start()
  })
  afterAll(() => brain?.stop())

  test('answers /test/reset with the clock at zero and holds no game', async () => {
    expect(await brain.reset()).toBe(0)
    expect(await brain.state()).toEqual({ game: null })
  })

  test('after a reset the robot has been set up and nothing else', async () => {
    await brain.reset()
    const calls = await brain.calls()
    expect(calls.map((c) => c.tool)).toEqual(SETUP)
    expect(calls[0]!.seq).toBe(1)
    expect(await brain.head()).toEqual({ yaw: 0, pitch: 25 })
    expect(await brain.screen()).toMatchObject({ face: 'idle', blink: true, showing: null })
    expect(await brain.said()).toEqual([])
  })

  test('advances its clock only when told, never backwards, and reset puts it back', async () => {
    await brain.reset()
    expect(await brain.advance(60)).toBe(60)
    expect(await brain.advance(0)).toBe(60)
    expect((await brain.request('POST', '/test/advance', { seconds: -1 })).status).toBe(400)
    expect(await brain.reset()).toBe(0)
  })

  test('what a test says is heard on the host\'s next listen', async () => {
    await brain.reset()
    await brain.hear('nothing to see here')
    await brain.advance(5)
    const listens = (await brain.calls()).filter((c) => c.tool === 'listen')
    expect(listens.map((c) => (c.answer as { text: string }).text)).toEqual(['nothing to see here'])
  })

  test('naming a game at a table of five: the head sweeps, the count is said, the deal begins', async () => {
    await brain.reset()
    await brain.table([-60, -30, 0, 30, 60].map((bearing) => ({ bearing })))
    await brain.hear("let's play mafia")
    await brain.advance(20)
    const said = await brain.said()
    expect(said[0]).toMatch(/^Five of you\./)
    expect(said).toContain('Player one, lean in.')
    expect((await brain.moves()).slice(1, 17)).toEqual([-90, -78, -66, -54, -42, -30, -18, -6, 6, 18, 30, 42, 54, 66, 78, 90])
    expect(await brain.state()).toMatchObject({ game: 'mafia', seats: 5 })
    expect((await brain.screen()).set).not.toBeNull()
  })

  test('frames pushed per pan are taken, and what is not an image is refused', async () => {
    await brain.reset()
    await brain.table([{ bearing: -40 }, { bearing: 40, pose: 'down' }], [-30, 0, 30])
    await brain.frame(renderTable(0, [{ bearing: 0 }, { bearing: 10, close: true }]))
    expect((await brain.request('POST', '/test/frame', new Uint8Array([1, 2, 3]), 'image/png')).status).toBe(400)
    expect((await brain.request('POST', '/test/table', { faces: [{ bearing: 'left' }] })).status).toBe(400)
  })

  test('a rig is taken and a malformed one refused', async () => {
    await brain.reset()
    await brain.rig('imposter', { word: 'beach', imposter: 3 })
    expect((await brain.request('POST', '/test/rig', { imposter: 3 })).status).toBe(400)
  })

  test('a dashboard write carries the test key (dashKey()), and is 403 without it', async () => {
    await brain.reset()
    expect((await brain.request('POST', '/dash/api/hear', { text: 'hello' })).status).toBe(403)
    const res = await fetch(brain.url + '/dash/api/hear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Dash-Key': dashKey() },
      body: JSON.stringify({ text: 'hello' }),
    })
    expect(res.status).toBe(200)
    expect(await res.json()).toEqual({ ok: true, pending: 1 })
    expect((await brain.request('GET', '/dash/api/events')).status).toBe(403)
    expect((await brain.request('GET', `/dash/api/events?key=${dashKey()}`)).status).toBe(200)
  })

  test('serves nothing it has not built', async () => {
    for (const path of ['/', '/voice/1.wav', '/test/nothing']) expect((await brain.request('GET', path)).status).toBe(404)
  })
})
