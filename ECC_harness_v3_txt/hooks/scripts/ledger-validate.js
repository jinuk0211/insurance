#!/usr/bin/env node
/**
 * hooks/scripts/ledger-validate.js
 *
 * findings_ledger.json Write 완료 후 실행되는 PostToolUse 훅.
 * 스키마 검증 + DRAFT 취약점의 retrieval_query 비어있지 않은지 확인.
 */

import { readFileSync, existsSync } from "fs"
import { resolve } from "path"

function main() {
  const ledgerPath = resolve("workspace/findings_ledger.json")
  if (!existsSync(ledgerPath)) {
    process.exit(0)
  }

  let data
  try {
    data = JSON.parse(readFileSync(ledgerPath, "utf-8"))
  } catch {
    console.error("[ledger-validate] ❌ JSON 파싱 실패 — findings_ledger.json 손상")
    process.exit(1)
  }

  const errors = []

  // 필수 필드
  if (!data.session_id) errors.push("session_id 누락")
  if (!data.product_type) errors.push("product_type 누락")
  if (!Array.isArray(data.clauses)) errors.push("clauses 배열 필수")

  // clause_id 유일성
  const ids = (data.clauses || []).map(c => c.clause_id)
  const dupes = ids.filter((id, i) => ids.indexOf(id) !== i)
  if (dupes.length) errors.push(`중복 clause_id: ${dupes.join(", ")}`)

  // DRAFT 취약점 검증
  for (const clause of data.clauses || []) {
    for (const flag of clause.vulnerability_flags || []) {
      if (flag.status === "DRAFT" || flag.status === "LOW_CONFIDENCE") {
        if (!flag.retrieval_query?.trim()) {
          errors.push(`${clause.clause_id}의 ${flag.vuln_id}: retrieval_query 비어있음`)
        }
        if (!flag.triggered_by?.trim()) {
          errors.push(`${clause.clause_id}의 ${flag.vuln_id}: triggered_by 비어있음`)
        }
        if (flag.precedent_refs?.length > 0) {
          errors.push(`${clause.clause_id}의 ${flag.vuln_id}: Stage 2에서 precedent_refs 채우면 안 됨`)
        }
      }
    }
  }

  if (errors.length > 0) {
    console.error("[ledger-validate] ❌ 스키마 오류:")
    errors.forEach(e => console.error(`  - ${e}`))
    process.exit(1)
  }

  const flagCount = (data.clauses || []).reduce(
    (s, c) => s + (c.vulnerability_flags?.length || 0), 0
  )
  console.log(`[ledger-validate] ✓ 검증 통과 (조항=${data.clauses?.length} 취약점DRAFT=${flagCount})`)
  process.exit(0)
}

main()
