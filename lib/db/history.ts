import { randomUUID } from "node:crypto"
import { eq, and, desc, gte } from "drizzle-orm"
import { getDb } from "./client"
import { insuranceDashboardSnapshot, insuranceQueryHistory } from "./schema"
import { encryptJson, decryptJson } from "@/lib/crypto"
import { deriveUserKey, maskName } from "@/lib/user-key"
import { getCodefEnv } from "@/lib/codef-client"
import { buildInsuranceDashboardModel } from "@/lib/insurance-dashboard"
import { getInsuranceCacheTtlMs } from "@/lib/insurance-cache-policy"

interface BaseParams {
  userName?: unknown
  birthDate?: unknown
  phoneNo?: unknown
}

export interface RecentQueryResult {
  data: unknown
  queriedAt: string
}

/** 최근 성공 조회가 있으면 복호화해 반환한다. 없거나 만료됐을 때만 CODEF를 호출한다. */
export async function getRecentQueryResult(
  baseParams: BaseParams,
  now = new Date(),
): Promise<RecentQueryResult | null> {
  if (!process.env.DATABASE_URL) return null

  const userKey = deriveUserKey(
    String(baseParams.phoneNo ?? ""),
    String(baseParams.birthDate ?? ""),
  )
  const ttlMs = getInsuranceCacheTtlMs(process.env.INSURANCE_CACHE_TTL_HOURS)
  const cutoff = new Date(now.getTime() - ttlMs)
  const userEnvironment = and(
    eq(insuranceQueryHistory.userKey, userKey),
    eq(insuranceQueryHistory.env, getCodefEnv()),
  )
  const rows = await getDb()
    .select({
      payloadCipher: insuranceQueryHistory.payloadCipher,
      queriedAt: insuranceQueryHistory.queriedAt,
    })
    .from(insuranceQueryHistory)
    .where(ttlMs > 0
      ? and(userEnvironment, gte(insuranceQueryHistory.queriedAt, cutoff))
      : userEnvironment)
    .orderBy(desc(insuranceQueryHistory.queriedAt))
    .limit(1)

  if (!rows.length) return null
  return {
    data: decryptJson(rows[0].payloadCipher),
    queriedAt: rows[0].queriedAt.toISOString(),
  }
}

/** 조회 성공 시 호출. 전체 결과를 암호화해 저장한다. */
export async function saveQueryHistory(
  baseParams: BaseParams,
  data: unknown,
  sourceKey?: string
): Promise<void> {
  const userKey = deriveUserKey(
    String(baseParams.phoneNo ?? ""),
    String(baseParams.birthDate ?? "")
  )
  const dashboard = buildInsuranceDashboardModel(data)
  const normalizedSourceKey = sourceKey?.trim() || null
  const historyId = normalizedSourceKey ?? randomUUID()
  const historyValues = {
    id: historyId,
    userKey,
    sourceKey: normalizedSourceKey,
    env: getCodefEnv(),
    nameMasked: maskName(String(baseParams.userName ?? "")),
    contractCount: dashboard.activeCount,
    totalPremium: dashboard.totalPremium,
    payloadCipher: encryptJson(data),
  }

  const snapshotValues = {
    historyId,
    activeCount: dashboard.activeCount,
    inactiveCount: dashboard.inactiveCount,
    totalPremium: dashboard.totalPremium,
    categoryCounts: dashboard.categoryCounts,
  }
  const db = getDb()

  await db.transaction(async (tx) => {
    await tx
      .insert(insuranceQueryHistory)
      .values(historyValues)
      .onConflictDoNothing()
    await tx
      .insert(insuranceDashboardSnapshot)
      .values(snapshotValues)
      .onConflictDoUpdate({
        target: insuranceDashboardSnapshot.historyId,
        set: {
          activeCount: dashboard.activeCount,
          inactiveCount: dashboard.inactiveCount,
          totalPremium: dashboard.totalPremium,
          categoryCounts: dashboard.categoryCounts,
          generatedAt: new Date(),
        },
      })
  })
}

export interface HistorySummary {
  id: string
  queriedAt: string
  env: string
  nameMasked: string | null
  contractCount: number
  totalPremium: number
}

export async function listQueryHistory(userKey: string): Promise<HistorySummary[]> {
  const rows = await getDb()
    .select({
      id: insuranceQueryHistory.id,
      queriedAt: insuranceQueryHistory.queriedAt,
      env: insuranceQueryHistory.env,
      nameMasked: insuranceQueryHistory.nameMasked,
      contractCount: insuranceQueryHistory.contractCount,
      totalPremium: insuranceQueryHistory.totalPremium,
    })
    .from(insuranceQueryHistory)
    .where(eq(insuranceQueryHistory.userKey, userKey))
    .orderBy(desc(insuranceQueryHistory.queriedAt))
    .limit(50)
  return rows.map((r) => ({ ...r, queriedAt: r.queriedAt.toISOString() }))
}

/** userKey가 일치할 때만 복호화 반환 (다른 사용자 이력 열람 차단). */
export async function getQueryHistoryItem(id: string, userKey: string): Promise<unknown | null> {
  const rows = await getDb()
    .select({ payloadCipher: insuranceQueryHistory.payloadCipher })
    .from(insuranceQueryHistory)
    .where(and(eq(insuranceQueryHistory.id, id), eq(insuranceQueryHistory.userKey, userKey)))
    .limit(1)
  if (!rows.length) return null
  return decryptJson(rows[0].payloadCipher)
}
