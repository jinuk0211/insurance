import { eq, sql } from "drizzle-orm"
import { getDb } from "./client"
import { codefApiUsage } from "./schema"
import {
  evaluateCodefCallBudget,
  resolveCodefCallLimit,
} from "@/lib/codef-budget-policy"

const BUDGET_LOCK_ID = 1_337_491_073

export class CodefApiBudgetExceededError extends Error {
  constructor(limit: number) {
    super(`CODEF API 안전 호출 한도(${limit}회)에 도달했습니다. 관리자 확인 후 다시 시도해주세요.`)
    this.name = "CodefApiBudgetExceededError"
  }
}

export async function reserveCodefApiCall(env: string, endpoint: string): Promise<string> {
  if (!process.env.DATABASE_URL) {
    throw new Error("CODEF 호출 보호를 위한 DATABASE_URL이 설정되지 않았습니다.")
  }

  const limit = resolveCodefCallLimit(process.env.CODEF_API_CALL_LIMIT)
  return getDb().transaction(async (tx) => {
    await tx.execute(sql`select pg_advisory_xact_lock(${BUDGET_LOCK_ID})`)
    const rows = await tx
      .select({ used: sql<number>`count(*)::int` })
      .from(codefApiUsage)
      .where(eq(codefApiUsage.env, env))
    const decision = evaluateCodefCallBudget(Number(rows[0]?.used ?? 0), limit)
    if (!decision.allowed) throw new CodefApiBudgetExceededError(limit)

    const inserted = await tx
      .insert(codefApiUsage)
      .values({ env, endpoint })
      .returning({ id: codefApiUsage.id })
    return inserted[0].id
  })
}

export async function completeCodefApiCall(
  id: string,
  status: "completed" | "failed",
): Promise<void> {
  await getDb()
    .update(codefApiUsage)
    .set({ status, completedAt: new Date() })
    .where(eq(codefApiUsage.id, id))
}
