import assert from "node:assert/strict"
import test from "node:test"

import { resolveReturningUserCheck } from "./returning-user-flow.ts"

test("continues with a valid saved registration session", () => {
  assert.deepEqual(
    resolveReturningUserCheck({ found: true, sessionId: "4a97144c-2a64-47b8-9d13-41ac8c17ef20" }),
    { action: "query", sessionId: "4a97144c-2a64-47b8-9d13-41ac8c17ef20" },
  )
})

test("routes a stale browser profile to one-time reconnection", () => {
  assert.deepEqual(resolveReturningUserCheck({ found: false }), { action: "reconnect" })
})

test("does not query when the server response has no session id", () => {
  assert.deepEqual(resolveReturningUserCheck({ found: true }), { action: "reconnect" })
})
