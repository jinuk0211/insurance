/**
 * 조회 이력 암호화 (AES-256-GCM).
 * 키: HISTORY_ENC_KEY (32바이트 base64). 서버 전용.
 * 저장 포맷: base64( iv(12) | authTag(16) | ciphertext )
 */

import { createCipheriv, createDecipheriv, randomBytes } from "crypto"

const IV_LEN = 12
const TAG_LEN = 16

function getKey(): Buffer {
  const key = Buffer.from(process.env.HISTORY_ENC_KEY || "", "base64")
  if (key.length !== 32) {
    throw new Error("HISTORY_ENC_KEY 환경변수가 32바이트 base64 값이어야 합니다.")
  }
  return key
}

export function encryptJson(obj: unknown): string {
  const iv = randomBytes(IV_LEN)
  const cipher = createCipheriv("aes-256-gcm", getKey(), iv)
  const plaintext = Buffer.from(JSON.stringify(obj), "utf8")
  const enc = Buffer.concat([cipher.update(plaintext), cipher.final()])
  const tag = cipher.getAuthTag()
  return Buffer.concat([iv, tag, enc]).toString("base64")
}

export function decryptJson<T = unknown>(payload: string): T {
  const buf = Buffer.from(payload, "base64")
  const iv = buf.subarray(0, IV_LEN)
  const tag = buf.subarray(IV_LEN, IV_LEN + TAG_LEN)
  const enc = buf.subarray(IV_LEN + TAG_LEN)
  const decipher = createDecipheriv("aes-256-gcm", getKey(), iv)
  decipher.setAuthTag(tag)
  const dec = Buffer.concat([decipher.update(enc), decipher.final()])
  return JSON.parse(dec.toString("utf8")) as T
}
