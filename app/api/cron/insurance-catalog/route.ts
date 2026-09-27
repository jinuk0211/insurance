import { NextRequest, NextResponse } from "next/server"
import { boundedInteger, isCronAuthorized } from "@/lib/catalog/cron-auth"
import { runInsuranceCatalogCollection } from "@/lib/catalog/collector"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"
export const maxDuration = 300

export async function GET(request: NextRequest) {
  const secret = process.env.CRON_SECRET
  const hasSecretAuthorization = isCronAuthorized(request.headers.get("authorization"), secret)
  if (!hasSecretAuthorization) {
    return NextResponse.json({ error: "인증되지 않은 수집 요청입니다." }, { status: 401 })
  }

  try {
    const result = await runInsuranceCatalogCollection({
      maxProducts: boundedInteger(process.env.CATALOG_MAX_PRODUCTS_PER_RUN, 3, 1, 10),
      snapshotLimit: boundedInteger(process.env.CATALOG_SNAPSHOT_LIMIT, 1, 0, 3),
    })
    return NextResponse.json(result, { headers: { "Cache-Control": "no-store" } })
  } catch (error) {
    const message = error instanceof Error ? error.message : "상품 공시 수집에 실패했습니다."
    return NextResponse.json({ error: message }, {
      status: 502,
      headers: { "Cache-Control": "no-store" },
    })
  }
}
