import test from "node:test"
import assert from "node:assert/strict"

import { checkSyntheticPolicyProof, SYNTHETIC_KB_POLICY_PROOF } from "./synthetic-policy-proof.ts"

test("synthetic certificate matches only the pinned KB PDF revision and citation", () => {
  const result = checkSyntheticPolicyProof(SYNTHETIC_KB_POLICY_PROOF)
  assert.equal(result.matched, true)
  assert.equal(result.checks.length, 6)
  assert.ok(result.checks.every((check) => check.matched))
  assert.equal(result.document?.sourceFileName, "25290_1_1.pdf")
  assert.equal(result.citation?.page, 118)
})

for (const [field, value] of [
  ["insurer", "다른보험사"],
  ["productName", "KB 9회주는 암보험Plus(무배당)(26.07)_2종_해약환급금 미지급형"],
  ["documentId", "kb-25033-2026-03-01"],
  ["versionKey", "2026-03-01"],
  ["pdfSha256", "0".repeat(64)],
  ["citationPage", 119],
  ["citationAnchor", "다른 문구"],
]) {
  test("synthetic certificate stays pending when " + field + " differs", () => {
    const result = checkSyntheticPolicyProof({ ...SYNTHETIC_KB_POLICY_PROOF, [field]: value })
    assert.equal(result.matched, false)
    assert.ok(result.checks.some((check) => !check.matched))
  })
}
