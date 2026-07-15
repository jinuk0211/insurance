import test from "node:test"
import assert from "node:assert/strict"

import {
  canAttemptCodefConfirmation,
  resolveCodefAuthMethod,
  toCaptchaImageSrc,
} from "./codef-flow.ts"

test("normalizes a raw CODEF captcha payload to an image data URL", () => {
  assert.equal(toCaptchaImageSrc("YWJjZA=="), "data:image/png;base64,YWJjZA==")
})

test("keeps an existing image data URL and rejects missing values", () => {
  const dataUrl = "data:image/jpeg;base64,YWJjZA=="
  assert.equal(toCaptchaImageSrc(dataUrl), dataUrl)
  assert.equal(toCaptchaImageSrc(null), null)
  assert.equal(toCaptchaImageSrc("javascript:alert(1)"), null)
})

test("maps CODEF auth method values to PASS or SMS", () => {
  assert.equal(resolveCodefAuthMethod("0"), "sms")
  assert.equal(resolveCodefAuthMethod("sms"), "sms")
  assert.equal(resolveCodefAuthMethod("1"), "pass")
  assert.equal(resolveCodefAuthMethod("pass"), "pass")
})

test("requires manual confirmation and caps it at three CODEF calls", () => {
  assert.equal(canAttemptCodefConfirmation(0), true)
  assert.equal(canAttemptCodefConfirmation(2), true)
  assert.equal(canAttemptCodefConfirmation(3), false)
})
