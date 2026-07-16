import assert from "node:assert/strict"
import test from "node:test"

import { normalizeDisclosureDate, stableFingerprint } from "./types.ts"

test("normalizes only valid eight-digit disclosure dates", () => {
  assert.equal(normalizeDisclosureDate("2026. 03. 01"), "2026-03-01")
  assert.equal(normalizeDisclosureDate("20260230"), null)
  assert.equal(normalizeDisclosureDate("판매중"), null)
})

test("creates the same fingerprint regardless of object key order", () => {
  assert.equal(stableFingerprint({ b: 2, a: { y: 2, x: 1 } }), stableFingerprint({ a: { x: 1, y: 2 }, b: 2 }))
})
