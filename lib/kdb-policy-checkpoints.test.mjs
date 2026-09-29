import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import {
  KDB_RENEWAL_POLICY_CHECKPOINTS,
  KDB_RENEWAL_POLICY_DOCUMENT_ID,
  KDB_RENEWAL_POLICY_SHA256,
  KDB_STANDARD_POLICY_CHECKPOINTS,
  KDB_STANDARD_POLICY_DOCUMENT_ID,
  KDB_STANDARD_POLICY_SHA256,
} from "./kdb-policy-checkpoints.ts"
import library from "./generated/official-policy-library.json" with { type: "json" }
import analysis from "./generated/official-policy-analysis.json" with { type: "json" }

for (const [id, sha256, pageCount, checkpoints] of [
  [KDB_RENEWAL_POLICY_DOCUMENT_ID, KDB_RENEWAL_POLICY_SHA256, 258, KDB_RENEWAL_POLICY_CHECKPOINTS],
  [KDB_STANDARD_POLICY_DOCUMENT_ID, KDB_STANDARD_POLICY_SHA256, 256, KDB_STANDARD_POLICY_CHECKPOINTS],
]) {
  test("advisor checkpoints cite pinned KDB PDF pages for " + id, () => {
    const document = library.documents.find((item) => item.id === id)
    const extracted = analysis.documents.find((item) => item.id === id)
    assert.ok(document)
    assert.ok(extracted)
    assert.equal(document.expectedSha256, sha256)
    assert.equal(extracted.sourceSha256, sha256)
    assert.equal(document.expectedPageCount, pageCount)
    assert.equal(extracted.pageCount, pageCount)
    assert.equal(document.analysisStartPage, 26)
    assert.equal(document.effectiveFrom, null)
    assert.equal(document.saleStatus, "unknown")
    assert.equal(checkpoints.length, 4)

    const source = readFileSync(new URL("../public/policy-texts/" + id + ".txt", import.meta.url), "utf8")
    const parts = source.split(/===== PAGE (\d+) \/ \d+ =====/)
    const pages = new Map()
    for (let index = 1; index < parts.length - 1; index += 2) {
      pages.set(Number(parts[index]), parts[index + 1].replace(/\s+/g, ""))
    }

    let checked = 0
    for (const item of checkpoints) {
      assert.ok(item.title && item.summary && item.advisorCheck)
      assert.ok(item.evidence.length > 0)
      for (const evidence of item.evidence) {
        assert.ok(evidence.article)
        assert.ok(evidence.page >= document.analysisStartPage && evidence.page <= pageCount)
        assert.ok(pages.get(evidence.page)?.includes(evidence.anchor.replace(/\s+/g, "")),
          id + ": " + item.title + ", PDF " + evidence.page + "쪽 근거 불일치")
        checked += 1
      }
    }
    assert.ok(checked >= 8)
    for (const section of [extracted.coverage, extracted.riders, extracted.exclusions, extracted.reduction, extracted.waiting]) {
      assert.ok(section.evidence.every((item) => item.page >= document.analysisStartPage))
    }
  })
}
