import assert from "node:assert/strict"
import test from "node:test"

import { getInsuranceCacheTtlMs, isInsuranceCacheFresh } from "./insurance-cache-policy.ts"

test("reuses a successful insurance query for 24 hours by default", () => {
  const now = new Date("2026-07-15T12:00:00.000Z")

  assert.equal(getInsuranceCacheTtlMs(undefined), 24 * 60 * 60 * 1000)
  assert.equal(
    isInsuranceCacheFresh(new Date("2026-07-14T12:00:00.001Z"), now, getInsuranceCacheTtlMs(undefined)),
    true,
  )
  assert.equal(
    isInsuranceCacheFresh(new Date("2026-07-14T12:00:00.000Z"), now, getInsuranceCacheTtlMs(undefined)),
    false,
  )
})

test("accepts a bounded cache TTL override and rejects invalid values", () => {
  assert.equal(getInsuranceCacheTtlMs("72"), 72 * 60 * 60 * 1000)
  assert.equal(getInsuranceCacheTtlMs("0"), 24 * 60 * 60 * 1000)
  assert.equal(getInsuranceCacheTtlMs("1000"), 24 * 60 * 60 * 1000)
  assert.equal(getInsuranceCacheTtlMs("invalid"), 24 * 60 * 60 * 1000)
})
