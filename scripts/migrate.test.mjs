import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import test from "node:test"

const script = fileURLToPath(new URL("./migrate.mjs", import.meta.url))
function runMigration(demo, args = []) {
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
    env: { ...process.env, DATABASE_URL: "", INSURANCE_DEMO_ONLY: demo },
  })
}

test("public demo build succeeds without a database only with its explicit build flag", () => {
  const result = runMigration("true", ["--skip-for-demo"])
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /공개 데모 빌드/)
})

test("a direct migration still requires the database even in demo mode", () => {
  const result = runMigration("true")
  assert.equal(result.status, 1)
  assert.match(result.stderr, /DATABASE_URL 없음/)
})

test("real-data builds fail closed when the database is missing", () => {
  const result = runMigration("false", ["--skip-for-demo"])
  assert.equal(result.status, 1)
  assert.match(result.stderr, /DATABASE_URL 없음/)
})

test("an unset demo mode does not skip database validation", () => {
  const result = runMigration("", ["--skip-for-demo"])
  assert.equal(result.status, 1)
  assert.match(result.stderr, /DATABASE_URL 없음/)
})
