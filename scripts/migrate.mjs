// 비대화형 마이그레이션 적용: drizzle/ 폴더의 생성된 SQL을 PostgreSQL에 적용한다.
import { existsSync, readFileSync } from "fs"
import { Pool } from "pg"
import { drizzle } from "drizzle-orm/node-postgres"
import { migrate } from "drizzle-orm/node-postgres/migrator"

// CI/운영 환경변수를 우선하고, 로컬 파일은 있을 때만 보완적으로 로드한다.
if (existsSync(".env.local")) {
  const env = readFileSync(".env.local", "utf8")
  for (const line of env.split(/\r?\n/)) {
    const m = line.match(/^([A-Z_]+)=(.*)$/)
    if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2]
  }
}

// 공개 데모는 DB를 사용하지 않으므로 빌드에서만 마이그레이션을 생략한다.
// 직접 실행한 db:migrate 및 실데이터 모드에서는 기존 검사를 유지한다.
if (process.argv.includes("--skip-for-demo") && process.env.INSURANCE_DEMO_ONLY === "true") {
  console.log("공개 데모 빌드: 데이터베이스 마이그레이션을 생략합니다.")
  process.exit(0)
}

const url = process.env.DATABASE_URL
if (!url) throw new Error("DATABASE_URL 없음")

const pool = new Pool({
  connectionString: url,
  max: 1,
  connectionTimeoutMillis: 10_000,
  allowExitOnIdle: true,
  ssl: process.env.DATABASE_SSL_REJECT_UNAUTHORIZED === "false"
    ? { rejectUnauthorized: false }
    : undefined,
})

try {
  const db = drizzle({ client: pool })
  await migrate(db, { migrationsFolder: "./drizzle" })
  console.log("✓ 마이그레이션 적용 완료")
} finally {
  await pool.end()
}
