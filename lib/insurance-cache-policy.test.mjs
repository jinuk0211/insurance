import assert from "node:assert/strict"
import test from "node:test"

import { getInsuranceCacheTtlMs, isInsuranceCacheFresh } from "./insurance-cache-policy.ts"

test("reuses a successful insurance query indefinitely by default", () => {
  const now = new Date("2026-07-15T12:00:00.000Z")

  assert.equal(getInsuranceCacheTtlMs(undefined), 0)
  assert.equal(
    isInsuranceCacheFresh(new Date("2020-01-01T00:00:00.000Z"), now, getInsuranceCacheTtlMs(undefined)),
    true,
  )
})

test("accepts a bounded cache TTL override and rejects invalid values", () => {
  assert.equal(getInsuranceCacheTtlMs("72"), 72 * 60 * 60 * 1000)
  assert.equal(getInsuranceCacheTtlMs("0"), 0)
  assert.equal(getInsuranceCacheTtlMs("1000"), 0)
  assert.equal(getInsuranceCacheTtlMs("invalid"), 0)
})
