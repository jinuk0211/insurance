import assert from "node:assert/strict"
import test from "node:test"

import { isPathAllowedByRobots } from "./robots.ts"

test("allows crawling when no group applies", () => {
  assert.equal(isPathAllowedByRobots("User-agent: Yeti\nDisallow: /private", "https://example.com/private", "KFinLegalBot"), true)
})

test("uses the longest matching allow or disallow rule", () => {
  const robots = "User-agent: *\nDisallow: /catalog\nAllow: /catalog/public"
  assert.equal(isPathAllowedByRobots(robots, "https://example.com/catalog/private", "KFinLegalBot"), false)
  assert.equal(isPathAllowedByRobots(robots, "https://example.com/catalog/public/file.pdf", "KFinLegalBot"), true)
})

test("prefers a specific user-agent group over the wildcard group", () => {
  const robots = "User-agent: *\nDisallow: /\n\nUser-agent: KFinLegalBot\nAllow: /catalog"
  assert.equal(isPathAllowedByRobots(robots, "https://example.com/catalog", "KFinLegalBot/1.0"), true)
})
