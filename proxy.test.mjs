import assert from "node:assert/strict"
import { afterEach, test } from "node:test"
import { NextRequest } from "next/server.js"

import { config, proxy } from "./proxy.ts"

const envKeys = [
  "NODE_ENV",
  "VERCEL",
  "INSURANCE_LOCAL_LIVE_TEST",
  "INSURANCE_DEMO_ONLY",
  "INSURANCE_PREVIEW_USER",
  "INSURANCE_PREVIEW_PASSWORD",
  "CODEF_CLIENT_ID",
  "CODEF_CLIENT_SECRET",
  "CODEF_PUBLIC_KEY",
]
const original = Object.fromEntries(envKeys.map((key) => [key, process.env[key]]))

afterEach(() => {
  for (const key of envKeys) {
    if (original[key] === undefined) delete process.env[key]
    else process.env[key] = original[key]
  }
})

function request(path, authorization) {
  return new NextRequest("https://insurance.example" + path, {
    headers: authorization ? { authorization } : undefined,
  })
}

function credentials() {
  process.env.CODEF_CLIENT_ID = "sandbox-client"
  process.env.CODEF_CLIENT_SECRET = "sandbox-secret"
  process.env.CODEF_PUBLIC_KEY = "sandbox-public-key"
  delete process.env.INSURANCE_DEMO_ONLY
}

test("covers both public pages and all live insurance and CODEF dataset APIs", () => {
  assert.deepEqual(config.matcher, [
    "/insurance/:path*",
    "/pension/:path*",
    "/api/insurance/:path*",
    "/api/codef-datasets/:path*",
  ])
})

test("keeps the synthetic insurance and pension pages public with security headers", () => {
  process.env.VERCEL = "1"
  for (const path of ["/insurance", "/insurance/terms", "/pension"]) {
    const response = proxy(request(path))
    assert.equal(response.status, 200)
    assert.equal(response.headers.get("x-middleware-next"), "1")
    assert.equal(response.headers.get("www-authenticate"), null)
    assert.equal(response.headers.get("cache-control"), "private, no-store")
    assert.equal(response.headers.get("x-frame-options"), "DENY")
  }
})

test("blocks every deployed live API even when CODEF and preview credentials exist", async () => {
  process.env.VERCEL = "1"
  process.env.NODE_ENV = "production"
  process.env.INSURANCE_LOCAL_LIVE_TEST = "true"
  process.env.INSURANCE_PREVIEW_USER = "reviewer"
  process.env.INSURANCE_PREVIEW_PASSWORD = "a-long-preview-password"
  credentials()
  const authorization = "Basic " + Buffer.from("reviewer:a-long-preview-password").toString("base64")
  for (const path of [
    "/api/insurance/check-user",
    "/api/insurance/history",
    "/api/insurance/query",
    "/api/insurance/register/start",
    "/api/codef-datasets/start",
  ]) {
    const response = proxy(request(path, authorization))
    assert.equal(response.status, 503, path)
    assert.equal(response.headers.get("www-authenticate"), null)
    assert.equal(response.headers.get("cache-control"), "private, no-store")
    assert.match((await response.json()).error, /GA 접근 인증/)
  }
})

test("blocks production live APIs outside Vercel", () => {
  process.env.NODE_ENV = "production"
  delete process.env.VERCEL
  process.env.INSURANCE_LOCAL_LIVE_TEST = "true"
  credentials()
  assert.equal(proxy(request("/api/insurance/history")).status, 503)
})

test("blocks local development unless live testing is explicitly enabled", () => {
  process.env.NODE_ENV = "development"
  delete process.env.VERCEL
  credentials()
  delete process.env.INSURANCE_LOCAL_LIVE_TEST
  assert.equal(proxy(request("/api/insurance/history")).status, 503)
})

test("keeps demo-only mode closed even with local opt-in", () => {
  process.env.NODE_ENV = "development"
  delete process.env.VERCEL
  process.env.INSURANCE_LOCAL_LIVE_TEST = "true"
  credentials()
  process.env.INSURANCE_DEMO_ONLY = "true"
  assert.equal(proxy(request("/api/codef-datasets/start")).status, 503)
})

test("requires CODEF credentials for local live testing", () => {
  process.env.NODE_ENV = "development"
  delete process.env.VERCEL
  process.env.INSURANCE_LOCAL_LIVE_TEST = "true"
  credentials()
  delete process.env.CODEF_PUBLIC_KEY
  assert.equal(proxy(request("/api/insurance/query")).status, 503)
})

test("allows explicit local live testing without forwarding Authorization", () => {
  process.env.NODE_ENV = "development"
  delete process.env.VERCEL
  process.env.INSURANCE_LOCAL_LIVE_TEST = "true"
  credentials()
  const response = proxy(request("/api/insurance/query", "Bearer local-test-token"))
  assert.equal(response.status, 200)
  assert.equal(response.headers.get("x-middleware-next"), "1")
  assert.equal(response.headers.get("x-middleware-request-authorization"), null)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})
