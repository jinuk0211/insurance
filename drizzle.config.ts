import { defineConfig } from "drizzle-kit"
import { readFileSync } from "fs"

// drizzle-kit은 .env.local을 자동 로드하지 않으므로 DATABASE_URL이 없으면 직접 읽어온다.
if (!process.env.DATABASE_URL) {
  try {
    const env = readFileSync(".env.local", "utf8")
    const match = env.match(/^DATABASE_URL=(.*)$/m)
    if (match) process.env.DATABASE_URL = match[1].trim()
  } catch {
    /* .env.local 없으면 무시 */
  }
}

export default defineConfig({
  schema: "./lib/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: { url: process.env.DATABASE_URL || "" },
})
