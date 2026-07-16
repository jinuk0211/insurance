import "server-only"

import { decryptJson, encryptJson } from "@/lib/crypto"

export const SUBJECT_ACCESS_COOKIE = "kfin_subject_access"
const MAX_AGE_SECONDS = 30 * 24 * 60 * 60

interface SubjectAccessToken {
  userKey: string
  expiresAt: number
}
export function createSubjectAccessToken(userKey: string, now = Date.now()): string {
  return encryptJson({
    userKey,
    expiresAt: now + MAX_AGE_SECONDS * 1000,
  } satisfies SubjectAccessToken)
}

export function verifySubjectAccessToken(
  token: string | undefined,
  userKey: string,
  now = Date.now(),
): boolean {
  if (!token) return false
  try {
    const parsed = decryptJson<SubjectAccessToken>(token)
    return parsed.userKey === userKey && parsed.expiresAt > now
  } catch {
    return false
  }
}

export const SUBJECT_ACCESS_COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "strict" as const,
  path: "/",
  maxAge: MAX_AGE_SECONDS,
}
