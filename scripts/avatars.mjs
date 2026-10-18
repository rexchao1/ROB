// The entry for `npm run build:avatars`: DiceBear's core and the one avatar style the
// dashboard draws seats with, bundled by esbuild into brain/dash/vendor/dicebear.js
// (one offline ES module; the table's network has no CDN). The page imports
//   import { createAvatar, style } from '/dash/vendor/dicebear.js'
// and draws createAvatar(style, avatar.options).toString() for a seat's avatar from
// GET /dash/api/state (brain/dash.py, seats_info). Licenses: brain/dash/vendor/LICENSES.md.
export { createAvatar } from '@dicebear/core'
export * as style from '@dicebear/lorelei'
