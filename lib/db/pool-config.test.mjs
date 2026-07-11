import assert from "node:assert/strict"
import test from "node:test"

import { createDatabasePoolOptions } from "./pool-config.ts"

const DATABASE_URL = "postgresql://user:password@example.com:5432/app"

test("uses conservative serverless pool defaults", () => {
  const options = createDatabasePoolOptions(DATABASE_URL)

  assert.equal(options.connectionString, DATABASE_URL)
  assert.equal(options.max, 3)
  assert.equal(options.idleTimeoutMillis, 5_000)
  assert.equal(options.connectionTimeoutMillis, 10_000)
  assert.equal(options.allowExitOnIdle, true)
  assert.equal(options.ssl, undefined)
})

test("clamps the configured pool size to a safe range", () => {
  assert.equal(createDatabasePoolOptions(DATABASE_URL, { poolMax: "0" }).max, 1)
  assert.equal(createDatabasePoolOptions(DATABASE_URL, { poolMax: "99" }).max, 10)
  assert.equal(createDatabasePoolOptions(DATABASE_URL, { poolMax: "invalid" }).max, 3)
})

test("allows Railway self-signed TLS only through an explicit opt-in", () => {
  const options = createDatabasePoolOptions(DATABASE_URL, {
    rejectUnauthorized: "false",
  })

  assert.deepEqual(options.ssl, { rejectUnauthorized: false })
})

test("rejects an empty database URL", () => {
  assert.throws(
    () => createDatabasePoolOptions("  "),
    /DATABASE_URL/,
  )
})
