import { NextRequest, NextResponse } from "next/server"
import { isCronAuthorized } from "@/lib/catalog/cron-auth"
import { getCatalogStatus } from "@/lib/catalog/repository"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: NextRequest) {
  if (!isCronAuthorized(request.headers.get("authorization"), process.env.CRON_SECRET)) {
    return NextResponse.json({ error: "인증되지 않은 상태 조회입니다." }, { status: 401 })
  }
  return NextResponse.json(await getCatalogStatus(), {
    headers: { "Cache-Control": "no-store" },
  })
}
