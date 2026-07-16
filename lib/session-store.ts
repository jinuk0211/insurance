/**
 * CODEF 멀티스텝 인증 세션 저장소.
 *
 * - DATABASE_URL 있으면: Postgres(codef_session) 백엔드 + 전체 암호화.
 *   Vercel 서버리스 다중 인스턴스/콜드스타트에서도 세션이 유지된다.
 * - DATABASE_URL 없으면: 메모리 Map 폴백 (로컬 개발용).
 *
 * 세션엔 자격증명(regPw/loginPw 등)이 들어가므로 DB 저장 시 항상 암호화하고
 * 20분 TTL로 만료시킨다.
 */

import { eq } from "drizzle-orm"
import { getDb } from "@/lib/db/client"
import { codefSession } from "@/lib/db/schema"
import { encryptJson, decryptJson } from "@/lib/crypto"

export interface CodefSession {
  baseParams: Record<string, unknown>
  twoWayInfo?: Record<string, unknown>
  queryTwoWayInfo?: Record<string, unknown>
  queryParams?: Record<string, unknown>
  step: "start" | "captcha" | "sms_or_pass" | "reg_info" | "email_auth" | "dataset_auth" | "done"
  datasetKey?: string
  datasetUserKey?: string
  datasetConfirmAttempts?: number
  regId?: string
  regPw?: string
  regEmail?: string
  finalId?: string
  finalPw?: string
  finalEmail?: string
  loginId?: string
  loginPw?: string
  updatedAt?: number
}

const TTL_MS = 20 * 60 * 1000

function useDb(): boolean {
  return Boolean(process.env.DATABASE_URL)
}

// ── 메모리 폴백 ───────────────────────────────────────────────────────────────
const mem = new Map<string, { session: CodefSession; expiresAt: number }>()

export async function getSession(id: string): Promise<CodefSession | undefined> {
  if (!useDb()) {
    const entry = mem.get(id)
    if (!entry) return undefined
    if (Date.now() > entry.expiresAt) {
      mem.delete(id)
      return undefined
    }
    return entry.session
  }

  const rows = await getDb()
    .select()
    .from(codefSession)
    .where(eq(codefSession.id, id))
    .limit(1)
  if (!rows.length) return undefined
  if (Date.now() > rows[0].expiresAt.getTime()) {
    await getDb().delete(codefSession).where(eq(codefSession.id, id))
    return undefined
  }
  return decryptJson<CodefSession>(rows[0].dataCipher)
}

export async function saveSession(
  id: string,
  patch: Partial<CodefSession>
): Promise<CodefSession> {
  const existing = (await getSession(id)) ?? ({} as CodefSession)
  const updated: CodefSession = { ...existing, ...patch, updatedAt: Date.now() }
  const expiresAt = new Date(Date.now() + TTL_MS)

  if (!useDb()) {
    mem.set(id, { session: updated, expiresAt: expiresAt.getTime() })
    return updated
  }

  const dataCipher = encryptJson(updated)
  await getDb()
    .insert(codefSession)
    .values({ id, dataCipher, expiresAt, updatedAt: new Date() })
    .onConflictDoUpdate({
      target: codefSession.id,
      set: { dataCipher, expiresAt, updatedAt: new Date() },
    })
  return updated
}

export async function deleteSession(id: string): Promise<void> {
  if (!useDb()) {
    mem.delete(id)
    return
  }
  await getDb().delete(codefSession).where(eq(codefSession.id, id))
}
