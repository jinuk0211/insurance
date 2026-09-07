#!/usr/bin/env node
/**
 * hooks/scripts/audit-logger.js
 *
 * workspace/*.json Write 완료 후 실행되는 PostToolUse 훅.
 * audit_trail.log에 이벤트를 기록한다.
 */

import { appendFileSync, existsSync, readFileSync } from "fs"
import { resolve, basename } from "path"

function main() {
  const filePath = process.argv[2] || ""
  const fileName = basename(filePath)
  const ts = new Date().toISOString()

  // 파일에서 session_id, stage 정보 추출
  let sessionId = "unknown"
  let stageInfo = ""

  try {
    const data = JSON.parse(readFileSync(resolve(filePath), "utf-8"))
    sessionId = data.session_id || "unknown"

    if (fileName === "contract_state.json") {
      stageInfo = `stage_completed=${data.stage_completed}`
    } else if (fileName === "findings_ledger.json") {
      const total = data.clauses?.length || 0
      const flagged = data.clauses?.filter(c => c.vulnerability_flags?.length > 0).length || 0
      stageInfo = `clauses=${total} flagged=${flagged}`
    } else if (fileName === "validated_findings.json") {
      const s = data.summary || {}
      stageInfo = `confirmed=${s.confirmed} rejected=${s.rejected} unverified=${s.unverified}`
    } else if (fileName === "final_report.json") {
      stageInfo = `risk=${data.overall_risk_level} findings=${data.findings?.length}`
    }
  } catch {
    // 읽기 실패해도 로그는 계속
  }

  const logLine = `[WRITE:${fileName}] session=${sessionId} ${stageInfo} ts=${ts}\n`
  const logPath = resolve("workspace/audit_trail.log")

  try {
    appendFileSync(logPath, logLine, "utf-8")
  } catch {
    // workspace/ 없으면 무시
  }

  process.exit(0)
}

main()
