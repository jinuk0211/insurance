/**
 * 등록 완료 사용자 저장소.
 * 같은 (전화번호+생년월일)로 다시 들어오면 재인증 없이 바로 조회하도록
 * credit4u 로그인 자격증명을 보관한다. 자격증명은 민감하므로 암호화 저장.
 *
 * - DATABASE_URL 있으면 Postgres(registered_user), 없으면 메모리 Map 폴백.
 */

import { eq } from "drizzle-orm"
import { getDb } from "./client"
import { registeredUser } from "./schema"
import { encryptJson, decryptJson } from "@/lib/crypto"
import { deriveUserKey } from "@/lib/user-key"

interface Cred {
  id: string
  pw: string
}

function useDb(): boolean {
  return Boolean(process.env.DATABASE_URL)
}

const mem = new Map<string, Cred>()

export async function findRegisteredUser(
  phoneNo: string,
  birthDate: string
): Promise<Cred | null> {
  const userKey = deriveUserKey(phoneNo, birthDate)

  if (!useDb()) {
    return mem.get(userKey) ?? null
  }

  const rows = await getDb()
    .select({ credCipher: registeredUser.credCipher })
    .from(registeredUser)
    .where(eq(registeredUser.userKey, userKey))
    .limit(1)
  if (!rows.length) return null
  return decryptJson<Cred>(rows[0].credCipher)
}

export async function saveRegisteredUser(
  phoneNo: string,
  birthDate: string,
  id: string,
  pw: string
): Promise<void> {
  const userKey = deriveUserKey(phoneNo, birthDate)

  if (!useDb()) {
    mem.set(userKey, { id, pw })
    return
  }

  const credCipher = encryptJson({ id, pw })
  await getDb()
    .insert(registeredUser)
    .values({ userKey, credCipher, updatedAt: new Date() })
    .onConflictDoUpdate({
      target: registeredUser.userKey,
      set: { credCipher, updatedAt: new Date() },
    })
}
