import { attachDatabasePool } from "@vercel/functions"
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres"
import { Pool } from "pg"
import * as schema from "./schema"
import { createDatabasePoolOptions } from "./pool-config"

type DB = NodePgDatabase<typeof schema>

let _db: DB | null = null
let _pool: Pool | null = null

/** 지연 초기화 — DATABASE_URL이 없을 때 import 시점이 아니라 쿼리 시점에 실패시킨다. */
export function getDb(): DB {
  if (_db) return _db
  const url = process.env.DATABASE_URL
  if (!url) {
    throw new Error("DATABASE_URL 환경변수가 설정되지 않았습니다.")
  }
  _pool = new Pool(createDatabasePoolOptions(url, {
    poolMax: process.env.DATABASE_POOL_MAX,
    rejectUnauthorized: process.env.DATABASE_SSL_REJECT_UNAUTHORIZED,
  }))
  if (process.env.VERCEL) attachDatabasePool(_pool)
  _db = drizzle({ client: _pool, schema })
  return _db
}
