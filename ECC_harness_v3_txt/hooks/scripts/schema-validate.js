#!/usr/bin/env node
/**
 * hooks/scripts/schema-validate.js
 *
 * final_report.json Write 직전 실행되는 PreToolUse 훅.
 * 리포트 스키마 + disclaimer 존재 + severity 유효값 검증.
 */

import { readFileSync } from "fs"
import { parseProposedWrite } from "./citation-gate.js"

const VALID_SEVERITIES = new Set(["CRITICAL", "HIGH", "MEDIUM", "LOW"])
const VALID_RISK_LEVELS = new Set(["HIGH", "MEDIUM", "LOW", "NONE"])

function main() {
  let data
  try {
    const content = readFileSync(0, "utf-8")
    const envelope = JSON.parse(content.replace(/^\uFEFF/, ""))
    const target = process.argv[2] || envelope?.tool_input?.file_path || ""
    if (!/(^|[\\/])final_report\.json$/.test(target)) {
      throw new Error("final_report.json target is required")
    }
    data = parseProposedWrite(content, process.argv[2])
  } catch (error) {
    console.error(`[schema-validate] ❌ proposed report 읽기 실패: ${error.message}`)
    process.exit(1)
  }

  const errors = []

  // 필수 필드
  const required = ["session_id", "generated_at", "overall_risk_level", "executive_summary", "findings", "disclaimer"]
  for (const f of required) {
    if (!data[f] && data[f] !== 0) errors.push(`${f} 누락`)
  }

  // overall_risk_level 유효값
  if (data.overall_risk_level && !VALID_RISK_LEVELS.has(data.overall_risk_level)) {
    errors.push(`overall_risk_level 유효하지 않음: ${data.overall_risk_level}`)
  }

  // disclaimer 필수
  if (typeof data.disclaimer !== "string" || !data.disclaimer.trim()) {
    errors.push("disclaimer 비어있음 — 필수")
  }

  // findings 검증
  const ranks = []
  if (!Array.isArray(data.findings)) errors.push("findings 배열 필수")
  for (const f of Array.isArray(data.findings) ? data.findings : []) {
    if (!f || typeof f !== "object" || Array.isArray(f)) {
      errors.push("finding 객체 필수")
      continue
    }
    if (!VALID_SEVERITIES.has(f.severity)) {
      errors.push(`finding ${f.vuln_id}: severity 유효하지 않음 (${f.severity})`)
    }
    if (typeof f.plain_language_explanation !== "string" || !f.plain_language_explanation.trim()) {
      errors.push(`finding ${f.vuln_id}: plain_language_explanation 비어있음`)
    }
    if (!Number.isInteger(f.rank) || f.rank < 1) errors.push("finding rank는 양의 정수 필수")
    ranks.push(f.rank)
  }

  // 순위 연속성
  const sortedRanks = [...ranks].sort((a, b) => a - b)
  const expectedRanks = Array.from({ length: ranks.length }, (_, i) => i + 1)
  if (JSON.stringify(sortedRanks) !== JSON.stringify(expectedRanks)) {
    errors.push(`findings 순위 불연속: ${sortedRanks.join(",")}`)
  }

  if (errors.length > 0) {
    console.error("[schema-validate] ❌ 스키마 오류 — final_report.json 저장 차단:")
    errors.forEach(e => console.error(`  - ${e}`))
    process.exit(1)
  }

  console.log(`[schema-validate] ✓ final_report 검증 통과 (risk=${data.overall_risk_level} findings=${data.findings?.length})`)
  process.exit(0)
}

main()
