import assert from "node:assert/strict"
import { afterEach, test } from "node:test"
import { NextRequest } from "next/server.js"

import { config, proxy } from "./proxy.ts"

const original = {
  NODE_ENV: process.env.NODE_ENV,
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
    ["NODE_ENV", original.NODE_ENV],
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

function uiRequest() {
  return new NextRequest("https://insurance.example/insurance")
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

test("applies the proxy security boundary to both the public UI and live API", () => {
  assert.deepEqual(config.matcher, ["/insurance/:path*", "/api/insurance/:path*"])
})

test("passes the public insurance UI without auth while preserving security headers", () => {
  process.env.INSURANCE_DEMO_ONLY = "true"

  const response = proxy(uiRequest())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("x-middleware-next"), "1")
  assert.equal(response.headers.get("www-authenticate"), null)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
  assert.equal(response.headers.get("x-frame-options"), "DENY")
})

test("shows the live demo-first UI without a browser login", () => {
  configurePreview()

  const response = proxy(uiRequest())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("x-middleware-next"), "1")
  assert.equal(response.headers.get("www-authenticate"), null)
})

test("never challenges the browser before exposing the live insurance UI", () => {
  configurePreview()

  const response = proxy(uiRequest())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("www-authenticate"), null)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})

test("passes the live insurance UI with exact preview credentials", () => {
  configurePreview()
  const authorization = `Basic ${Buffer.from("reviewer:a-long-preview-password").toString("base64")}`
  const response = proxy(new NextRequest("https://insurance.example/insurance", {
    headers: { authorization },
  }))

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("x-middleware-next"), "1")
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})

test("passes the live API without a browser login challenge", async () => {
  configurePreview()
  const response = proxy(request())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("www-authenticate"), null)
  assert.equal(response.headers.get("x-middleware-next"), "1")
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

test("does not require preview credentials in a deployment", () => {
  process.env.VERCEL = "1"
  process.env.CODEF_CLIENT_ID = "sandbox-client"
  process.env.CODEF_CLIENT_SECRET = "sandbox-secret"
  process.env.CODEF_PUBLIC_KEY = "sandbox-public-key"
  delete process.env.INSURANCE_PREVIEW_USER
  delete process.env.INSURANCE_PREVIEW_PASSWORD

  const response = proxy(request())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})

test("allows a production live API outside Vercel without Basic Auth", () => {
  process.env.NODE_ENV = "production"
  delete process.env.VERCEL
  process.env.CODEF_CLIENT_ID = "sandbox-client"
  process.env.CODEF_CLIENT_SECRET = "sandbox-secret"
  process.env.CODEF_PUBLIC_KEY = "sandbox-public-key"
  delete process.env.INSURANCE_PREVIEW_USER
  delete process.env.INSURANCE_PREVIEW_PASSWORD
  delete process.env.INSURANCE_DEMO_ONLY

  const response = proxy(request())

  assert.equal(response.status, 200)
  assert.equal(response.headers.get("www-authenticate"), null)
})
