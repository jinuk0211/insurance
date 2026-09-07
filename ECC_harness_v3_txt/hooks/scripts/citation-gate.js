#!/usr/bin/env node
/**
 * Pre-write citation existence gate. Reads proposed JSON from stdin (fd 0),
 * either directly with a target path argument or inside a PreToolUse Write
 * envelope. Never validates old on-disk content in place of the proposed write.
 *
 * Run from the harness/project directory containing data/*.json:
 *   node hooks/scripts/citation-gate.js [target_path] < proposed-write.json
 * Exit 2 blocks PreToolUse. Existence is NOT entailment or legal validity.
 */

import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { fileURLToPath } from "node:url"

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value)
const isText = (value) => typeof value === "string" && value.trim().length > 0
const normalize = (value) => value.replace(/\s+/g, "").toLowerCase()

function requireValue(condition, message) {
  if (!condition) throw new Error(message)
}

function parseJson(content, label) {
  requireValue(isText(content), `${label}: proposed content is missing`)
  try {
    return JSON.parse(content.replace(/^\uFEFF/, ""))
  } catch {
    throw new Error(`${label}: invalid JSON`)
  }
}

export function parseProposedWrite(content, pathArgument) {
  const input = parseJson(content, "stdin")
  requireValue(isObject(input), "proposed write must be an object")
  const isEnvelope = "tool_input" in input || "tool_name" in input || "hook_event_name" in input
  if (!isEnvelope) {
    requireValue(isText(pathArgument), "standalone proposed JSON requires a target path")
    return input
  }
  requireValue(input.tool_name === "Write", "only full-content Write envelopes are supported")
  requireValue(!("hook_event_name" in input) || input.hook_event_name === "PreToolUse", "expected PreToolUse envelope")
  requireValue(isObject(input.tool_input), "tool_input must be an object")
  requireValue(isText(input.tool_input.file_path), "tool_input.file_path is required")
  if (isText(pathArgument)) {
    requireValue(resolve(pathArgument) === resolve(input.tool_input.file_path), "target path argument does not match tool_input.file_path")
  }
  return parseJson(input.tool_input.content, "tool_input.content")
}

function validateStatutesDb(db) {
  requireValue(isObject(db), "statutes DB must be an object")
  if ("statutes" in db) {
    requireValue(Array.isArray(db.statutes) && db.statutes.length > 0, "statutes DB requires a nonempty statutes array")
    for (const law of db.statutes) {
      requireValue(isObject(law) && isText(law.law_name), "statutes DB contains a malformed law")
      requireValue(law.aliases === undefined || (Array.isArray(law.aliases) && law.aliases.every(isText)), "statutes DB aliases must be strings")
      requireValue(Array.isArray(law.articles) && law.articles.length > 0 && law.articles.every((article) => isObject(article) && isText(article.number)), "statutes DB contains malformed articles")
    }
    return db.statutes
  }
  // Retain the historical law-name -> article-number list schema.
  requireValue(Object.keys(db).length > 0, "statutes DB is empty")
  return Object.entries(db).map(([law_name, articles]) => {
    requireValue(isText(law_name) && Array.isArray(articles) && articles.length > 0 && articles.every(isText), "statutes DB map contains malformed articles")
    return { law_name, articles: articles.map((number) => ({ number })) }
  })
}

export function validateCitations(data, statutesDb, precedentsDb) {
  const laws = validateStatutesDb(statutesDb)
  requireValue(Array.isArray(precedentsDb) && precedentsDb.every((entry) => isObject(entry) && isText(entry.case_number)), "precedents DB must contain case_number records")
  requireValue(isObject(data) && Array.isArray(data.findings), "findings must be an explicit array in an object")
  const counts = data.findings.map((finding, index) => {
    const label = `findings[${index}]`
    requireValue(isObject(finding) && isText(finding.vuln_id), `${label}: vuln_id is required`)
    const grounds = finding.legal_grounds
    requireValue(isObject(grounds), `${label}: legal_grounds must be an object`)
    requireValue(Array.isArray(grounds.statutes) && Array.isArray(grounds.precedents), `${label}: statutes and precedents must be explicit arrays`)
    requireValue(grounds.dispute_cases === undefined || (Array.isArray(grounds.dispute_cases) && grounds.dispute_cases.length === 0), `${label}: dispute case citations are unsupported without a trusted database`)

    for (const statute of grounds.statutes) {
      requireValue(isObject(statute) && isText(statute.law_name) && isText(statute.article), `${label}: malformed statute citation`)
      // Model-provided verified flags never participate in the trust decision.
      const law = laws.find((entry) => [entry.law_name, ...(entry.aliases ?? [])].some((name) => normalize(name) === normalize(statute.law_name)))
      requireValue(law && law.articles.some((article) => normalize(article.number) === normalize(statute.article)), `${label}: statute ID not found in local DB (${statute.law_name} ${statute.article})`)
    }
    for (const precedent of grounds.precedents) {
      requireValue(isObject(precedent) && isText(precedent.case_number), `${label}: malformed precedent citation`)
      requireValue(precedentsDb.some((entry) => normalize(entry.case_number) === normalize(precedent.case_number)), `${label}: precedent ID not found in local DB (${precedent.case_number})`)
    }
    return grounds.statutes.length + grounds.precedents.length
  })
  return { findings: data.findings.length, citations: counts.reduce((sum, count) => sum + count, 0), scope: "local_database_id_existence_only" }
}

export function main() {
  try {
    requireValue(!process.stdin.isTTY, "proposed content must be provided on stdin")
    const data = parseProposedWrite(readFileSync(0, "utf8"), process.argv[2])
    // Missing, unreadable or malformed reference data must fail closed.
    const statutes = parseJson(readFileSync(resolve("data/statutes_db.json"), "utf8"), "statutes DB")
    const precedents = parseJson(readFileSync(resolve("data/precedents.json"), "utf8"), "precedents DB")
    const result = validateCitations(data, statutes, precedents)
    console.log(`[citation-gate] PASS: ${result.citations} citation IDs exist in local DB; entailment and legal validity NOT verified`)
    process.exitCode = 0
  } catch (error) {
    console.error(`[citation-gate] BLOCKED: ${error.message}`)
    process.exitCode = 2
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main()
