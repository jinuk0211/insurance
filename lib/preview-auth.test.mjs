import assert from "node:assert/strict"
import test from "node:test"

import { evaluatePreviewAuth } from "./preview-auth.ts"

const configured = {
  isDeployed: true,
  expectedUser: "reviewer",
  expectedPassword: "a-long-preview-password",
}

function basic(user, password) {
  return `Basic ${Buffer.from(`${user}:${password}`).toString("base64")}`
}

test("allows local development when preview credentials are absent", () => {
  const result = evaluatePreviewAuth(null, {
    isDeployed: false,
    expectedUser: undefined,
    expectedPassword: undefined,
  })

  assert.equal(result.allowed, true)
})

test("fails closed on a deployment when preview credentials are absent", () => {
  const result = evaluatePreviewAuth(null, {
    isDeployed: true,
    expectedUser: undefined,
    expectedPassword: undefined,
  })

  assert.deepEqual(result, { allowed: false, status: 503 })
})

test("challenges missing or malformed authorization", () => {
  assert.deepEqual(evaluatePreviewAuth(null, configured), { allowed: false, status: 401 })
  assert.deepEqual(evaluatePreviewAuth("Bearer nope", configured), { allowed: false, status: 401 })
  assert.deepEqual(evaluatePreviewAuth("Basic not-base64", configured), { allowed: false, status: 401 })
})

test("rejects incorrect credentials", () => {
  assert.deepEqual(
    evaluatePreviewAuth(basic("reviewer", "wrong"), configured),
    { allowed: false, status: 401 },
  )
})

test("accepts exact preview credentials", () => {
  assert.deepEqual(
    evaluatePreviewAuth(basic("reviewer", "a-long-preview-password"), configured),
    { allowed: true },
  )
})
