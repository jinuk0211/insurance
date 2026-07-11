/**
 * 로그인 없는 앱에서 조회 이력을 사용자별로 묶기 위한 불투명 식별자.
 * 평문 PII를 저장하지 않도록 (전화번호 + 생년월일)을 HMAC-SHA256 해시한다.
 * 서버 전용 (USER_KEY_SECRET 사용).
 */

import { createHmac } from "crypto"

export function deriveUserKey(phoneNo: string, birthDate: string): string {
  const secret = process.env.USER_KEY_SECRET || ""
  if (!secret) {
    throw new Error("USER_KEY_SECRET 환경변수가 설정되지 않았습니다.")
  }
  const phone = String(phoneNo).replace(/\D/g, "")
  const birth = String(birthDate).replace(/\D/g, "")
  return createHmac("sha256", secret).update(`${phone}|${birth}`).digest("hex")
}

/** 화면 표시용 이름 마스킹 (홍길동 → 홍*동). */
export function maskName(name: string): string {
  const n = (name || "").trim()
  if (n.length <= 1) return n || "-"
  if (n.length === 2) return `${n[0]}*`
  return `${n[0]}${"*".repeat(n.length - 2)}${n[n.length - 1]}`
}
