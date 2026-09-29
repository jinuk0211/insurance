import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import { NHLIFE_POLICY_CHECKPOINTS, NHLIFE_POLICY_DOCUMENT_ID, NHLIFE_POLICY_SHA256 } from "./nhlife-policy-checkpoints.ts"
import library from "./generated/official-policy-library.json" with { type: "json" }
import analysis from "./generated/official-policy-analysis.json" with { type: "json" }

test("advisor checkpoints cite the pinned NH Life dementia PDF pages", () => {
  const document = library.documents.find((item) => item.id === NHLIFE_POLICY_DOCUMENT_ID)
  const extracted = analysis.documents.find((item) => item.id === NHLIFE_POLICY_DOCUMENT_ID)
  assert.ok(document)
  assert.ok(extracted)
  assert.equal(document.expectedSha256, NHLIFE_POLICY_SHA256)
  assert.equal(extracted.sourceSha256, NHLIFE_POLICY_SHA256)
  assert.equal(document.expectedPageCount, 328)
  assert.equal(extracted.pageCount, 328)
  assert.equal(document.analysisStartPage, 39)
  assert.equal(document.effectiveFrom, null)
  assert.equal(document.saleStatus, "on_sale")
  assert.equal(NHLIFE_POLICY_CHECKPOINTS.length, 5)

  const source = readFileSync(new URL("../public/policy-texts/" + NHLIFE_POLICY_DOCUMENT_ID + ".txt", import.meta.url), "utf8")
  const parts = source.split(/===== PAGE (\d+) \/ \d+ =====/)
  const pages = new Map()
  for (let index = 1; index < parts.length - 1; index += 2) {
    pages.set(Number(parts[index]), parts[index + 1].replace(/\s+/g, ""))
  }

  let checked = 0
  for (const item of NHLIFE_POLICY_CHECKPOINTS) {
    assert.ok(item.title && item.summary && item.advisorCheck)
    assert.ok(item.evidence.length > 0)
    for (const evidence of item.evidence) {
      assert.ok(evidence.article)
      assert.ok(evidence.page >= document.analysisStartPage && evidence.page <= document.expectedPageCount)
      assert.ok(pages.get(evidence.page)?.includes(evidence.anchor.replace(/\s+/g, "")),
        item.title + ": PDF " + evidence.page + "쪽 근거 불일치")
      checked += 1
    }
  }
  assert.ok(checked >= 12)
  for (const section of [extracted.coverage, extracted.riders, extracted.exclusions, extracted.reduction, extracted.waiting]) {
    assert.ok(section.evidence.every((item) => item.page >= document.analysisStartPage))
  }
})
