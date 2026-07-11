import { NextResponse } from "next/server"

export function GET() {
  return NextResponse.json({
    ok: true,
    service: "kfin-insurance",
    databaseConfigured: Boolean(process.env.DATABASE_URL),
    codefEnvironment: process.env.CODEF_ENV ?? "unconfigured",
  })
}
