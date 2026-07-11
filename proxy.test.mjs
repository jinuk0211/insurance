import assert from "node:assert/strict"
import { afterEach, test } from "node:test"
import { NextRequest } from "next/server.js"

import { config, proxy } from "./proxy.ts"

const original = {
  VERCEL: process.env.VERCEL,
  user: process.env.INSURANCE_PREVIEW_USER,
  password: process.env.INSURANCE_PREVIEW_PASSWORD,
}

afterEach(() => {
  for (const [key, value] of [
    ["VERCEL", original.VERCEL],
    ["INSURANCE_PREVIEW_USER", original.user],
    ["INSURANCE_PREVIEW_PASSWORD", original.password],
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
}

test("protects both the insurance UI and API", () => {
  assert.deepEqual(config.matcher, ["/insurance/:path*", "/api/insurance/:path*"])
})

test("returns a private Basic challenge before an insurance handler runs", () => {
  configurePreview()
  const response = proxy(request())

  assert.equal(response.status, 401)
  assert.equal(response.headers.get("www-authenticate"), 'Basic realm="KFin Insurance Preview", charset="UTF-8"')
  assert.equal(response.headers.get("cache-control"), "private, no-store")
  assert.equal(response.headers.get("x-frame-options"), "DENY")
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
  delete process.env.INSURANCE_PREVIEW_USER
  delete process.env.INSURANCE_PREVIEW_PASSWORD

  const response = proxy(request())

  assert.equal(response.status, 503)
  assert.equal(response.headers.get("cache-control"), "private, no-store")
})
