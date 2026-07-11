import assert from "node:assert/strict"
import { afterEach, test } from "node:test"
import { NextRequest } from "next/server.js"

import { config, proxy } from "./proxy.ts"

const original = {
  VERCEL: process.env.VERCEL,
  user: process.env.INSURANCE_PREVIEW_USER,
  password: process.env.INSURANCE_PREVIEW_PASSWORD,
  demoOnly: process.env.INSURANCE_DEMO_ONLY,
  codefClientId: process.env.CODEF_CLIENT_ID,
  codefClientSecret: process.env.CODEF_CLIENT_SECRET,
  codefPublicKey: process.env.CODEF_PUBLIC_KEY,
}

afterEach(() => {
  for (const [key, value] of [
    ["VERCEL", original.VERCEL],
    ["INSURANCE_PREVIEW_USER", original.user],
    ["INSURANCE_PREVIEW_PASSWORD", original.password],
    ["INSURANCE_DEMO_ONLY", original.demoOnly],
    ["CODEF_CLIENT_ID", original.codefClientId],
    ["CODEF_CLIENT_SECRET", original.codefClientSecret],
    ["CODEF_PUBLIC_KEY", original.codefPublicKey],
  ]) {
    if (value === undefined) delete process.env[key]
    else process.env[key] = value
  }
})

function request(authorization) {
  const headers = authorization ? { authorization } : undefined
  return new NextRequest("https://insurance.example/api/insurance/history", { headers })
}

function configurePreview() {
  process.env.VERCEL = "1"
  process.env.INSURANCE_PREVIEW_USER = "reviewer"
  process.env.INSURANCE_PREVIEW_PASSWORD = "a-long-preview-password"
  process.env.CODEF_CLIENT_ID = "sandbox-client"
  process.env.CODEF_CLIENT_SECRET = "sandbox-secret"
  process.env.CODEF_PUBLIC_KEY = "sandbox-public-key"
  delete process.env.INSURANCE_DEMO_ONLY
}

test("keeps the insurance UI public and gates only its live API", () => {
  assert.deepEqual(config.matcher, ["/api/insurance/:path*"])
})

test("returns JSON without a browser login challenge before an insurance handler runs", async () => {
  configurePreview()
  const response = proxy(request())

  assert.equal(response.status, 401)
  assert.equal(response.headers.get("www-authenticate"), null)
  assert.match((await response.json()).error, /authorization/i)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
  assert.equal(response.headers.get("x-frame-options"), "DENY")
})

test("fails closed in public demo mode without opening a browser login prompt", async () => {
  process.env.VERCEL = "1"
  process.env.INSURANCE_DEMO_ONLY = "true"
  delete process.env.CODEF_CLIENT_ID
  delete process.env.CODEF_CLIENT_SECRET
  delete process.env.CODEF_PUBLIC_KEY

  const response = proxy(request())

  assert.equal(response.status, 503)
  assert.equal(response.headers.get("www-authenticate"), null)
  assert.match((await response.json()).error, /데모 모드/)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})

test("passes exact credentials without forwarding the Authorization header", () => {
  configurePreview()
  const authorization = `Basic ${Buffer.from("reviewer:a-long-preview-password").toString("base64")}`
  const response = proxy(request(authorization))

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("x-middleware-next"), "1")
  assert.equal(response.headers.get("x-middleware-request-authorization"), null)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})

test("returns 503 when deployed without configured preview credentials", () => {
  process.env.VERCEL = "1"
  process.env.CODEF_CLIENT_ID = "sandbox-client"
  process.env.CODEF_CLIENT_SECRET = "sandbox-secret"
  process.env.CODEF_PUBLIC_KEY = "sandbox-public-key"
  delete process.env.INSURANCE_PREVIEW_USER
  delete process.env.INSURANCE_PREVIEW_PASSWORD

  const response = proxy(request())

  assert.equal(response.status, 503)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})
