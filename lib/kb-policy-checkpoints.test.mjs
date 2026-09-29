import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import {
  KB_POLICY_CHECKPOINTS,
  KB_POLICY_DOCUMENT_ID,
  KB_POLICY_SHA256,
} from "./kb-policy-checkpoints.ts"
import library from "./generated/official-policy-library.json" with { type: "json" }
import analysis from "./generated/official-policy-analysis.json" with { type: "json" }

test("advisor checkpoints cite the pinned KB 26.07 PDF and exact pages", () => {
  const document = library.documents.find((item) => item.id === KB_POLICY_DOCUMENT_ID)
  const extracted = analysis.documents.find((item) => item.id === KB_POLICY_DOCUMENT_ID)
  assert.ok(document)
  assert.ok(extracted)
  assert.equal(document.expectedSha256, KB_POLICY_SHA256)
  assert.equal(document.expectedPageCount, 774)
  assert.equal(extracted.sourceSha256, KB_POLICY_SHA256)
  assert.equal(document.pdfUrl, "https://www.kbinsure.co.kr/CG802030003.ec?fileNm=25290_1_1.pdf")
  assert.equal(KB_POLICY_CHECKPOINTS.length, 6)

  const source = readFileSync(new URL("../public/policy-texts/kb-25290-2026-07-01.txt", import.meta.url), "utf8")
  const parts = source.split(/===== PAGE (\d+) \/ 774 =====/)
  const pages = new Map()
  for (let index = 1; index < parts.length - 1; index += 2) {
    pages.set(Number(parts[index]), parts[index + 1].replace(/\s+/g, ""))
  }

  let checked = 0
  for (const item of KB_POLICY_CHECKPOINTS) {
    assert.ok(item.title && item.summary && item.advisorCheck)
    assert.ok(item.evidence.length > 0)
    for (const evidence of item.evidence) {
      assert.ok(evidence.article)
      assert.ok(evidence.page > 0 && evidence.page <= extracted.pageCount)
      assert.ok(pages.get(evidence.page)?.includes(evidence.anchor.replace(/\s+/g, "")),
        item.title + ": PDF " + evidence.page + "쪽 근거 불일치")
      checked += 1
    }
  }
  assert.equal(checked, 17)
})
