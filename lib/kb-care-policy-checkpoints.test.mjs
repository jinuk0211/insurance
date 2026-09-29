import { readFileSync } from "node:fs"
import test from "node:test"
import assert from "node:assert/strict"

import { KB_CARE_NO_REFUND_CHECKPOINTS, KB_CARE_POLICY_CHECKPOINTS, KB_CARE_POLICY_DOCUMENT_IDS, KB_CARE_POLICY_SHA256 } from "./kb-care-policy-checkpoints.ts"
import library from "./generated/official-policy-library.json" with { type: "json" }
import analysis from "./generated/official-policy-analysis.json" with { type: "json" }

test("KB 26.09 care checkpoints cite both pinned product entries and exact PDF pages", () => {
  const checkpointGroups = [KB_CARE_POLICY_CHECKPOINTS, KB_CARE_NO_REFUND_CHECKPOINTS]
  assert.equal(KB_CARE_POLICY_CHECKPOINTS.length, 5)
  assert.equal(KB_CARE_NO_REFUND_CHECKPOINTS.length, 6)

  for (const [index, id] of KB_CARE_POLICY_DOCUMENT_IDS.entries()) {
    const document = library.documents.find((item) => item.id === id)
    const extracted = analysis.documents.find((item) => item.id === id)
    assert.ok(document)
    assert.ok(extracted)
    assert.equal(document.pdfUrl, "https://www.kbinsure.co.kr/CG802030003.ec?fileNm=" + (index ? "25470" : "25469") + "_1_1.pdf")
    assert.equal(document.expectedSha256, KB_CARE_POLICY_SHA256)
    assert.equal(extracted.sourceSha256, KB_CARE_POLICY_SHA256)
    assert.equal(document.byteLength, 11568250)
    assert.equal(document.expectedPageCount, 388)
    assert.equal(extracted.pageCount, 388)

    const source = readFileSync(new URL("../public/policy-texts/" + id + ".txt", import.meta.url), "utf8")
    const parts = source.split(/===== PAGE (\d+) \/ 388 =====/)
    const pages = new Map()
    for (let part = 1; part < parts.length - 1; part += 2) {
      pages.set(Number(parts[part]), parts[part + 1].replace(/\s+/g, ""))
    }
    assert.equal(pages.size, 388)

    for (const item of checkpointGroups[index]) {
      assert.ok(item.title && item.summary && item.advisorCheck)
      assert.ok(item.evidence.length)
      for (const evidence of item.evidence) {
        assert.ok(evidence.page > 0 && evidence.page <= 388)
        assert.ok(pages.get(evidence.page)?.includes(evidence.anchor.replace(/\s+/g, "")),
          id + " " + item.title + ": PDF " + evidence.page + "쪽 근거 불일치: " + evidence.anchor)
      }
    }
  }
})
