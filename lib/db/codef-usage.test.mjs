import assert from "node:assert/strict"
import test from "node:test"

import { evaluateCodefCallBudget, resolveCodefCallLimit } from "../codef-budget-policy.ts"

test("keeps twenty calls in reserve when the account quota is one hundred", () => {
  assert.equal(resolveCodefCallLimit(undefined), 80)
  assert.equal(resolveCodefCallLimit("90"), 90)
  assert.equal(resolveCodefCallLimit("0"), 80)
  assert.equal(resolveCodefCallLimit("101"), 80)
})

test("allows a missing database result to consume one call and stops at the limit", () => {
  assert.deepEqual(evaluateCodefCallBudget(0, 80), { allowed: true, remainingAfter: 79 })
  assert.deepEqual(evaluateCodefCallBudget(79, 80), { allowed: true, remainingAfter: 0 })
  assert.deepEqual(evaluateCodefCallBudget(80, 80), { allowed: false, remainingAfter: 0 })
})
