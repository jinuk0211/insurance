import { and, eq } from "drizzle-orm"
import { encryptJson, decryptJson } from "@/lib/crypto"
import { getCodefEnv } from "@/lib/codef-client"
import type { CodefDatasetKey } from "@/lib/codef-dataset-definitions"
import type { CodefDatasetResult } from "@/lib/codef-dataset-normalizer"
import { getDb } from "@/lib/db/client"
import { codefDatasetSnapshot, phiAccessAudit } from "@/lib/db/schema"

export interface CachedDatasetResult {
  data: CodefDatasetResult
  queriedAt: string
}
async function audit(
  userKey: string,
  datasetKey: CodefDatasetKey,
  action: "read" | "write",
  resourceId: string,
): Promise<void> {
  await getDb().insert(phiAccessAudit).values({
    userKey,
    datasetKey,
    action,
    resourceId,
  })
}

export async function getDatasetSnapshot(
  userKey: string,
  datasetKey: CodefDatasetKey,
): Promise<CachedDatasetResult | null> {
  if (!process.env.DATABASE_URL) return null
  const rows = await getDb()
    .select({
      id: codefDatasetSnapshot.id,
      payloadCipher: codefDatasetSnapshot.payloadCipher,
      queriedAt: codefDatasetSnapshot.queriedAt,
    })
    .from(codefDatasetSnapshot)
    .where(and(
      eq(codefDatasetSnapshot.userKey, userKey),
      eq(codefDatasetSnapshot.datasetKey, datasetKey),
      eq(codefDatasetSnapshot.env, getCodefEnv()),
    ))
    .limit(1)

  if (!rows.length) return null
  await audit(userKey, datasetKey, "read", rows[0].id)
  return {
    data: decryptJson<CodefDatasetResult>(rows[0].payloadCipher),
    queriedAt: rows[0].queriedAt.toISOString(),
  }
}

export async function saveDatasetSnapshot(
  userKey: string,
  datasetKey: CodefDatasetKey,
  data: CodefDatasetResult,
): Promise<string> {
  if (!process.env.DATABASE_URL) {
    throw new Error("의료·연금 데이터 저장을 위한 DATABASE_URL이 설정되지 않았습니다.")
  }
  const rows = await getDb()
    .insert(codefDatasetSnapshot)
    .values({
      userKey,
      datasetKey,
      env: getCodefEnv(),
      payloadCipher: encryptJson(data),
    })
    .onConflictDoUpdate({
      target: [
        codefDatasetSnapshot.userKey,
        codefDatasetSnapshot.datasetKey,
        codefDatasetSnapshot.env,
      ],
      set: {
        payloadCipher: encryptJson(data),
        queriedAt: new Date(),
        updatedAt: new Date(),
      },
    })
    .returning({ id: codefDatasetSnapshot.id })

  const resourceId = rows[0].id
  await audit(userKey, datasetKey, "write", resourceId)
  return resourceId
}
