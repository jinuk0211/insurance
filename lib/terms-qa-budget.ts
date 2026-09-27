import { createHmac } from "node:crypto"
import { sql } from "drizzle-orm"
import { getDb } from "./db/client.ts"

export class QaBudgetExceeded extends Error {}
export async function reserveQaRequest(clientAddress: string): Promise<void> {
  if (!process.env.DATABASE_URL || !process.env.USER_KEY_SECRET) throw new Error("QA usage protection unavailable")
  const now = Date.now()
  const day = new Date(now + 9 * 3600_000).toISOString().slice(0, 10)
  const hash = createHmac("sha256", process.env.USER_KEY_SECRET).update(clientAddress).digest("hex").slice(0, 32)
  const buckets = [
    { key: "day:" + day, limit: 300, expires: new Date(now + 2 * 86400_000) },
    { key: "client:" + hash + ":" + Math.floor(now / 300_000), limit: 10, expires: new Date(now + 600_000) },
  ]
  await getDb().transaction(async (tx) => {
    await tx.execute(sql`select pg_advisory_xact_lock(187314921)`)
    await tx.execute(sql`create table if not exists terms_qa_usage (
      bucket text primary key, used integer not null, expires_at timestamptz not null
    )`)
    await tx.execute(sql`delete from terms_qa_usage where expires_at < now()`)
    for (const bucket of buckets) {
      const result = await tx.execute(sql`
        insert into terms_qa_usage (bucket, used, expires_at) values (${bucket.key}, 1, ${bucket.expires})
        on conflict (bucket) do update set used = terms_qa_usage.used + 1
        where terms_qa_usage.used < ${bucket.limit}
        returning used
      `)
      if (!result.rows.length) throw new QaBudgetExceeded("Question limit reached")
    }
  })
}

