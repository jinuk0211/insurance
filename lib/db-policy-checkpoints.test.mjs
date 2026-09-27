import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import {
  DB_POLICY_CHECKPOINTS,
  DB_POLICY_DOCUMENT_ID,
  DB_POLICY_SHA256,
} from "./db-policy-checkpoints.ts"
import library from "./generated/official-policy-library.json" with { type: "json" }
import analysis from "./generated/official-policy-analysis.json" with { type: "json" }

test("advisor checkpoints cite the pinned DB cancer PDF and exact pages", () => {
  const document = library.documents.find((item) => item.id === DB_POLICY_DOCUMENT_ID)
  const extracted = analysis.documents.find((item) => item.id === DB_POLICY_DOCUMENT_ID)
  assert.ok(document)
  assert.ok(extracted)
  assert.equal(document.expectedSha256, DB_POLICY_SHA256)
  assert.equal(extracted.sourceSha256, DB_POLICY_SHA256)
  assert.equal(document.effectiveFrom, null)
  assert.equal(document.analysisStartPage, 38)
  assert.equal(DB_POLICY_CHECKPOINTS.length, 5)

  const source = readFileSync(new URL("../public/policy-texts/db-direct-cancer-2607.txt", import.meta.url), "utf8")
  const parts = source.split(/===== PAGE (\d+) \/ 314 =====/)
  const pages = new Map()
  for (let index = 1; index < parts.length - 1; index += 2) {
    pages.set(Number(parts[index]), parts[index + 1].replace(/\s+/g, ""))
  }

  let checked = 0
  for (const item of DB_POLICY_CHECKPOINTS) {
    assert.ok(item.title && item.summary && item.advisorCheck)
    assert.ok(item.evidence.length > 0)
    for (const evidence of item.evidence) {
      assert.ok(evidence.article)
      assert.ok(evidence.page >= document.analysisStartPage && evidence.page <= extracted.pageCount)
      assert.ok(pages.get(evidence.page)?.includes(evidence.anchor.replace(/\s+/g, "")),
        `${item.title}: PDF ${evidence.page}쪽 근거 불일치`)
      checked += 1
    }
  }
  assert.equal(checked, 12)
  for (const section of [extracted.coverage, extracted.riders, extracted.exclusions, extracted.reduction, extracted.waiting]) {
    assert.ok(section.evidence.every((item) => item.page >= document.analysisStartPage))
  }
})
