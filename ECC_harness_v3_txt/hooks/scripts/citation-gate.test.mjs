import test from "node:test"
import assert from "node:assert/strict"
import { spawnSync } from "node:child_process"
import { existsSync, mkdtempSync, readFileSync, rmdirSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join, matchesGlob, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { parseProposedWrite, validateCitations } from "./citation-gate.js"

const script = join(dirname(fileURLToPath(import.meta.url)), "citation-gate.js")
const projectRoot = resolve(dirname(script), "../../..")
const statutes = JSON.parse(readFileSync(join(projectRoot, "data/statutes_db.json"), "utf8"))
const precedents = JSON.parse(readFileSync(join(projectRoot, "data/precedents.json"), "utf8"))
const knownStatute = { law_name: statutes.statutes[0].law_name, article: statutes.statutes[0].articles[0].number }
const knownPrecedent = { case_number: precedents[0].case_number }
const validFinding = () => ({ vuln_id: "INS-01", legal_grounds: { statutes: [knownStatute], precedents: [knownPrecedent], dispute_cases: [] } })
const proposal = (finding = validFinding()) => ({ findings: [finding] })

function runGate(input, options = {}) {
  const target = options.target ?? join(projectRoot, "workspace/nonexistent-citation-gate-test.json")
  return spawnSync(process.execPath, [script, ...(options.noArgument ? [] : [target])], {
    cwd: options.cwd ?? projectRoot,
    input: typeof input === "string" ? input : JSON.stringify(input),
    encoding: "utf8",
  })
}

function assertBlocked(result) {
  assert.equal(result.error, undefined)
  assert.equal(result.status, 2, result.stdout + result.stderr)
  assert.match(result.stderr, /\[citation-gate\]/)
}

test("invalid citations block a proposed write even when its target does not exist", () => {
  const target = join(projectRoot, "workspace/nonexistent-citation-gate-test.json")
  assert.equal(existsSync(target), false)
  const finding = validFinding()
  finding.legal_grounds.statutes = [{ law_name: "NONEXISTENT_TEST_LAW", article: "Article 999999" }]
  assertBlocked(runGate(proposal(finding), { target }))
  assert.equal(existsSync(target), false)
})

test("model supplied verified true cannot bypass unknown statute rejection", () => {
  const finding = validFinding()
  finding.legal_grounds.statutes = [{ law_name: "NONEXISTENT_TEST_LAW", article: "Article 999999", verified: true }]
  assertBlocked(runGate(proposal(finding)))
})

test("malformed JSON and missing proposed content fail closed", () => {
  assertBlocked(runGate("{bad json"))
  assertBlocked(runGate(""))
})

test("all claimed citations are checked against the actual local databases", () => {
  const result = runGate(proposal())
  assert.equal(result.status, 0, result.stderr)
  assert.match(result.stdout, /2/)
})

test("real PreToolUse Write envelope validates proposed tool_input.content", () => {
  const target = join(projectRoot, "workspace/nonexistent-citation-gate-test.json")
  const envelope = { hook_event_name: "PreToolUse", tool_name: "Write", tool_input: { file_path: target, content: JSON.stringify(proposal()) } }
  assert.equal(runGate(envelope, { noArgument: true }).status, 0)
  const finding = validFinding()
  finding.legal_grounds.precedents = [{ case_number: "NONEXISTENT_TEST_CASE" }]
  assertBlocked(runGate({ ...envelope, tool_input: { ...envelope.tool_input, content: JSON.stringify(proposal(finding)) } }))
})

test("an existing file cannot substitute for the proposed invalid overwrite", () => {
  const target = join(projectRoot, "data/statutes_db.json")
  const original = readFileSync(target)
  assertBlocked(runGate("{bad json", { target }))
  assertBlocked(runGate("", { target }))
  assert.deepEqual(readFileSync(target), original)
})

test("malformed findings and citation containers cannot silently pass as empty", () => {
  for (const data of [null, [], {}, { findings: {} }, { findings: [null] }, { findings: [{}] }, { findings: [{ vuln_id: "INS-01", legal_grounds: {} }] }]) {
    assertBlocked(runGate(data))
  }
  for (const ground of [null, { statutes: "not-array", precedents: [] }, { statutes: [null], precedents: [] }, { statutes: [], precedents: [{}] }]) {
    assertBlocked(runGate(proposal({ vuln_id: "INS-01", legal_grounds: ground })))
  }
})

test("missing databases fail closed instead of accepting fallback citations", () => {
  const cwd = mkdtempSync(join(tmpdir(), "citation-gate-test-"))
  try {
    assertBlocked(runGate(proposal(), { cwd }))
  } finally {
    rmdirSync(cwd)
  }
})

test("empty findings are an explicit valid result, not a parse fallback", () => {
  const result = runGate({ findings: [] })
  assert.equal(result.status, 0, result.stderr)
})

test("a known law does not make an unknown article valid", () => {
  const finding = validFinding()
  finding.legal_grounds.statutes = [{ ...knownStatute, article: "Article 999999", verified: true }]
  assertBlocked(runGate(proposal(finding)))
})

test("unsupported or incomplete hook envelopes fail closed", () => {
  const envelope = { hook_event_name: "PreToolUse", tool_name: "Write", tool_input: { file_path: "target.json", content: JSON.stringify(proposal()) } }
  for (const invalid of [
    { ...envelope, tool_name: "Edit" },
    { ...envelope, hook_event_name: "PostToolUse" },
    { ...envelope, tool_input: null },
    { ...envelope, tool_input: { content: "{}" } },
    { ...envelope, tool_input: { file_path: "target.json" } },
    { ...envelope, tool_input: { file_path: "target.json", content: proposal() } },
  ]) {
    assert.throws(() => parseProposedWrite(JSON.stringify(invalid)))
  }
  assert.throws(() => parseProposedWrite(JSON.stringify(envelope), "different-target.json"), /does not match/)
  assert.throws(() => parseProposedWrite(JSON.stringify(proposal())), /requires a target path/)
  assert.deepEqual(parseProposedWrite(JSON.stringify(envelope), "target.json"), proposal())
})

test("UTF-8 BOM and database-declared aliases are supported without relaxing article matching", () => {
  const db = { statutes: [{ law_name: "Test Law", aliases: ["Known Alias"], articles: [{ number: "Article 1" }] }] }
  const finding = { vuln_id: "TEST", legal_grounds: { statutes: [{ law_name: " known alias ", article: "Article  1" }], precedents: [] } }
  assert.equal(validateCitations(parseProposedWrite("\uFEFF" + JSON.stringify(proposal(finding)), "target.json"), db, []).citations, 1)
})

test("historical law-to-article-list database structure still validates exact IDs", () => {
  const finding = { vuln_id: "TEST", legal_grounds: { statutes: [{ law_name: "Test Law", article: "Article 1" }], precedents: [] } }
  assert.equal(validateCitations(proposal(finding), { "Test Law": ["Article 1"] }, []).citations, 1)
})

test("malformed trusted databases fail closed", () => {
  for (const db of [null, [], {}, { statutes: [] }, { statutes: [null] }, { statutes: [{ law_name: "Law", aliases: "bad", articles: [{ number: "1" }] }] }, { statutes: [{ law_name: "Law", articles: [{}] }] }, { "Law": [null] }]) {
    assert.throws(() => validateCitations(proposal(), db, precedents))
  }
  for (const db of [null, {}, [null], [{}]]) {
    assert.throws(() => validateCitations(proposal(), statutes, db), /precedents DB/)
  }
})

test("unverified dispute cases cannot bypass the supported citation databases", () => {
  const finding = validFinding()
  finding.legal_grounds.dispute_cases = [{ case_number: "UNKNOWN_DISPUTE" }]
  assertBlocked(runGate(proposal(finding)))
})

test("documented plugin registration selects nested validated findings and executes its stdin gate", () => {
  const pluginRoot = resolve(dirname(script), "../..")
  const config = JSON.parse(readFileSync(join(pluginRoot, "hooks/hooks.json"), "utf8"))
  assert.ok(config.hooks?.PreToolUse, "plugin hook file must have a top-level hooks object")
  const registration = config.hooks.PreToolUse.find((entry) => entry.hooks.some((hook) => hook.args?.some((arg) => arg.includes("citation-gate.js"))))
  assert.ok(registration)
  assert.equal(registration.matcher, "Write")
  const handler = registration.hooks[0]
  assert.equal(handler.if, "Write(**/validated_findings.json)")
  assert.equal(handler.command, "node")
  assert.equal(handler.async, undefined)
  assert.deepEqual(handler.args, ["${CLAUDE_PLUGIN_ROOT}/hooks/scripts/citation-gate.js"])
  const filePattern = handler.if.slice("Write(".length, -1)
  for (const target of ["workspace/validated_findings.json", "workspace/profile/product/validated_findings.json", "workspace\\profile\\product\\validated_findings.json"]) {
    assert.equal(matchesGlob(target.replaceAll("\\", "/"), filePattern), true)
    const args = handler.args.map((arg) => arg.replace("${CLAUDE_PLUGIN_ROOT}", pluginRoot))
    const envelope = { hook_event_name: "PreToolUse", tool_name: "Write", tool_input: { file_path: target, content: "{bad json" } }
    assertBlocked(spawnSync(handler.command, args, { cwd: projectRoot, input: JSON.stringify(envelope), encoding: "utf8" }))
    envelope.tool_input.content = JSON.stringify(proposal())
    const valid = spawnSync(handler.command, args, { cwd: projectRoot, input: JSON.stringify(envelope), encoding: "utf8" })
    assert.equal(valid.status, 0, valid.stderr)
  }
  assert.equal(matchesGlob("workspace/final_report.json", filePattern), false)
})
