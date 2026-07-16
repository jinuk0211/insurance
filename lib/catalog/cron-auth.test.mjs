import assert from "node:assert/strict"
import test from "node:test"

import { boundedInteger, isCatalogCronAuthorized, isCronAuthorized } from "./cron-auth.ts"

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

test("accepts Vercel's scheduler identity only as a no-secret fallback", () => {
  assert.equal(isCatalogCronAuthorized(null, undefined, "vercel-cron/1.0", true), true)
  assert.equal(isCatalogCronAuthorized(null, undefined, "vercel-cron/1.0", false), false)
  assert.equal(isCatalogCronAuthorized(null, "configured", "vercel-cron/1.0", true), false)
})
