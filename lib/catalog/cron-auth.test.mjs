import assert from "node:assert/strict"
import test from "node:test"

import { boundedInteger, isCronAuthorized } from "./cron-auth.ts"

test("requires an exact bearer secret", () => {
  assert.equal(isCronAuthorized("Bearer expected", "expected"), true)
  assert.equal(isCronAuthorized("Bearer wrong", "expected"), false)
  assert.equal(isCronAuthorized(null, "expected"), false)
  assert.equal(isCronAuthorized("Bearer expected", undefined), false)
})

test("bounds collector batch settings", () => {
  assert.equal(boundedInteger("5", 3, 1, 10), 5)
  assert.equal(boundedInteger("99", 3, 1, 10), 10)
  assert.equal(boundedInteger("invalid", 3, 1, 10), 3)
})

test("never authorizes cron collection without a configured bearer secret", () => {
  assert.equal(isCronAuthorized(null, undefined), false)
  assert.equal(isCronAuthorized("Bearer spoofed", undefined), false)
  assert.equal(isCronAuthorized("Bearer spoofed", ""), false)
})
