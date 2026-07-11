import type { PoolConfig } from "pg"

const DEFAULT_POOL_MAX = 3
const MIN_POOL_MAX = 1
const MAX_POOL_MAX = 10

interface PoolEnvironment {
  poolMax?: string
  rejectUnauthorized?: string
}

export function createDatabasePoolOptions(
  databaseUrl: string,
  environment: PoolEnvironment = {},
): PoolConfig {
  const connectionString = databaseUrl.trim()
  if (!connectionString) {
    throw new Error("DATABASE_URL 환경변수가 설정되지 않았습니다.")
  }

  const requestedMax = Number.parseInt(environment.poolMax ?? "", 10)
  const max = Number.isFinite(requestedMax)
    ? Math.min(MAX_POOL_MAX, Math.max(MIN_POOL_MAX, requestedMax))
    : DEFAULT_POOL_MAX
  const allowSelfSignedCertificate = environment.rejectUnauthorized === "false"

  return {
    connectionString,
    max,
    idleTimeoutMillis: 5_000,
    connectionTimeoutMillis: 10_000,
    allowExitOnIdle: true,
    ssl: allowSelfSignedCertificate ? { rejectUnauthorized: false } : undefined,
  }
}
