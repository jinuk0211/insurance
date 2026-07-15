/**
 * CODEF API Client - 내보험다보여 (credit4u)
 * Secure server-side only module
 *
 * Fixes from original server.js:
 * - Token expiry: 1 hour instead of 6 days
 * - RSA key validation: throws clearly if PUBKEY is missing
 * - codefPost: decodes URL-encoded JSON responses correctly
 */

import NodeRSA from "node-rsa"
import { completeCodefApiCall, reserveCodefApiCall } from "@/lib/db/codef-usage"

const ENV = {
  BASE:
    process.env.CODEF_ENV === "production"
      ? "https://api.codef.io"
      : process.env.CODEF_ENV === "demo"
        ? "https://development.codef.io"
        : "https://sandbox.codef.io",
  OAUTH: "https://oauth.codef.io/oauth/token",
  CID: process.env.CODEF_CLIENT_ID || "",
  SECRET: process.env.CODEF_CLIENT_SECRET || "",
  PUBKEY: process.env.CODEF_PUBLIC_KEY || "",
}

// ── Token cache (1-hour expiry, not 6 days) ───────────────────────────────────
let _token: string | null = null
let _tokenExp = 0

export async function getCodefToken(): Promise<string> {
  if (_token && Date.now() < _tokenExp) return _token
  if (!ENV.CID || !ENV.SECRET) {
    throw new Error("CODEF_CLIENT_ID 또는 CODEF_CLIENT_SECRET 환경변수가 설정되지 않았습니다.")
  }
  const auth = Buffer.from(`${ENV.CID}:${ENV.SECRET}`).toString("base64")
  const resp = await fetch(ENV.OAUTH, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${auth}`,
    },
    body: "grant_type=client_credentials&scope=read",
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`CODEF OAuth 실패 (${resp.status}): ${text}`)
  }
  const data = await resp.json()
  _token = data.access_token as string
  _tokenExp = Date.now() + 60 * 60 * 1000 // 1 hour
  return _token
}

// ── RSA encryption ────────────────────────────────────────────────────────────
export function rsaEncrypt(plain: string): string {
  if (!plain) return ""
  if (!ENV.PUBKEY) {
    throw new Error("CODEF_PUBLIC_KEY 환경변수가 설정되지 않았습니다.")
  }
  const key = new NodeRSA()
  key.importKey(
    `-----BEGIN PUBLIC KEY-----\n${ENV.PUBKEY}\n-----END PUBLIC KEY-----`,
    "pkcs8-public"
  )
  key.setOptions({ encryptionScheme: "pkcs1" })
  return key.encrypt(plain, "base64")
}

// ── CODEF POST ────────────────────────────────────────────────────────────────
// CODEF 응답은 단계별로 data 형상이 달라 각 라우트에서 필요한 필드를 판별한다.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function codefPost(endpoint: string, params: Record<string, unknown>): Promise<any> {
  const token = await getCodefToken()
  const reservationId = await reserveCodefApiCall(getCodefEnv(), endpoint)
  try {
    const resp = await fetch(`${ENV.BASE}${endpoint}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: encodeURIComponent(JSON.stringify(params)),
    })

    const text = await resp.text()
    let parsed: unknown
    try {
      parsed = JSON.parse(decodeURIComponent(text))
    } catch {
      try {
        parsed = JSON.parse(text)
      } catch {
        throw new Error(`CODEF 응답 파싱 실패: ${text.slice(0, 200)}`)
      }
    }
    await completeCodefApiCall(reservationId, "completed")
    return parsed
  } catch (error) {
    try {
      await completeCodefApiCall(reservationId, "failed")
    } catch (usageError) {
      console.error("CODEF 호출 로그 완료 처리 실패:", usageError)
    }
    throw error
  }
}

export function getCodefEnv(): "sandbox" | "demo" | "production" {
  if (ENV.BASE.includes("sandbox")) return "sandbox"
  if (ENV.BASE.includes("development")) return "demo"
  return "production"
}
