import assert from "node:assert/strict"
import test from "node:test"
import { BlobPreconditionFailedError } from "@vercel/blob"
import { QaBudgetExceeded, reserveDailyQuota } from "./terms-qa-budget.ts"

function store(initial) {
  let count = initial
  let revision = 0
  const reads = []
  const writes = []
  return {
    reads, writes, count: () => count,
    async get(path, options) {
      reads.push({ path, options })
      if (count === undefined) return null
      return { statusCode: 200, stream: new Response(JSON.stringify({ used: count })).body, blob: { etag: String(revision) } }
    },
    async put(path, body, options) {
      if ((count !== undefined && !options.allowOverwrite) || (options.ifMatch !== undefined && options.ifMatch !== String(revision))) throw new BlobPreconditionFailedError()
      count = JSON.parse(body).used
      revision++
      writes.push({ path, body, options })
    },
  }
}
const now = Date.UTC(2026, 8, 27, 14)

test("shared quota allows only one of concurrent requests at the daily boundary", async () => {
  const storage = store(299)
  const results = await Promise.allSettled(Array.from({ length: 4 }, () => reserveDailyQuota(storage, now)))
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1)
  assert.ok(results.filter((r) => r.status === "rejected").every((r) => r.reason instanceof QaBudgetExceeded))
  assert.equal(storage.count(), 300)
  assert.ok(storage.reads.every((r) => r.options.useCache === false))
})

test("concurrent first requests cannot reset or lose the daily counter", async () => {
  const storage = store(undefined)
  await Promise.all([reserveDailyQuota(storage, now), reserveDailyQuota(storage, now)])
  assert.equal(storage.count(), 2)
  assert.equal(storage.writes[0].options.allowOverwrite, false)
  assert.equal(storage.writes[1].options.ifMatch, "1")
  assert.equal(storage.writes[0].path, "terms-qa-usage/2026-09-27.json")
  assert.deepEqual(Object.keys(JSON.parse(storage.writes[0].body)), ["used"])
})

test("quota store failures and corrupted counters never permit model requests", async () => {
  await assert.rejects(reserveDailyQuota(store(-1), now), /Invalid quota state/)
  await assert.rejects(reserveDailyQuota(store(300), now), QaBudgetExceeded)
  const storage = store(3)
  storage.get = async () => { throw new Error("storage unavailable") }
  await assert.rejects(reserveDailyQuota(storage, now), /storage unavailable/)
  assert.equal(storage.writes.length, 0)
})
