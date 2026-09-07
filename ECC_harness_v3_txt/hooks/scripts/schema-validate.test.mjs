import test from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const script = fileURLToPath(new URL('./schema-validate.js', import.meta.url))
const valid = () => ({
  session_id: 'test', generated_at: '2026-09-07T00:00:00Z',
  overall_risk_level: 'LOW', executive_summary: 'Experimental report.',
  findings: [{ rank: 1, severity: 'LOW', vuln_id: 'INS-01', plain_language_explanation: 'Review required.' }],
  disclaimer: 'Not legal advice.',
})
const run = (data, args = ['workspace/final_report.json', 'final_report']) =>
  spawnSync(process.execPath, [script, ...args], {
    input: typeof data === 'string' ? data : JSON.stringify(data), encoding: 'utf8',
  })

test('reads valid proposed report from portable stdin', () => {
  assert.equal(run(valid()).status, 0)
})
test('does not pass invalid JSON or empty stdin on Windows', () => {
  assert.notEqual(run('{').status, 0)
  assert.notEqual(run('').status, 0)
})
test('validates proposed Write content, not the envelope', () => {
  const envelope = { tool_name: 'Write', hook_event_name: 'PreToolUse',
    tool_input: { file_path: 'workspace/final_report.json', content: JSON.stringify(valid()) } }
  assert.equal(run(envelope, []).status, 0)
  envelope.tool_input.content = '{}'
  assert.notEqual(run(envelope, []).status, 0)
})
for (const [label, mutate] of [
  ['missing rank', r => { delete r.findings[0].rank }],
  ['duplicate rank', r => { r.findings.push({ ...r.findings[0] }) }],
  ['non-array findings', r => { r.findings = {} }],
  ['null finding', r => { r.findings = [null] }],
  ['bad disclaimer type', r => { r.disclaimer = 5 }],
  ['missing disclaimer', r => { delete r.disclaimer }],
  ['bad risk', r => { r.overall_risk_level = 'CRITICAL' }],
]) {
  test(`blocks ${label}`, () => {
    const report = valid()
    mutate(report)
    assert.notEqual(run(report).status, 0)
  })
}
test('allows explicit empty findings', () => {
  const report = valid()
  report.findings = []
  report.overall_risk_level = 'NONE'
  assert.equal(run(report).status, 0)
})
test('cannot silently bypass validation with unknown target', () => {
  assert.notEqual(run({}, ['unknown.json']).status, 0)
})
