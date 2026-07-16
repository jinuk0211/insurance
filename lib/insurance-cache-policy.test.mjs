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

test("expires a cached query exactly at the configured cutoff", () => {
  const now = new Date("2026-07-16T12:00:00.000Z")
  const ttl = 60 * 60 * 1000
  assert.equal(isInsuranceCacheFresh(new Date("2026-07-16T11:00:01.000Z"), now, ttl), true)
  assert.equal(isInsuranceCacheFresh(new Date("2026-07-16T11:00:00.000Z"), now, ttl), false)
})
