import { defineConfig } from 'vitest/config'

// Two Vitest projects. The fast lane runs `features` (filtered by FEATURES);
// the full lane runs both. `integration` spawns the Python app and opens
// loopback sockets, so it stays out of the fast lane. Every project loads
// test/setup/no-network.ts: no test reaches past loopback.
export default defineConfig({
  test: {
    setupFiles: ['test/setup/no-network.ts'],
    projects: [
      { extends: true, test: { name: 'integration', include: ['test/integration/**/*.test.ts'], fileParallelism: false, testTimeout: 30_000, hookTimeout: 30_000 } },
      // A bound scenario drives the app on its virtual clock; nothing waits real time.
      { extends: true, test: { name: 'features', include: ['test/features.test.ts'], testTimeout: 30_000, hookTimeout: 30_000 } },
    ],
  },
})
