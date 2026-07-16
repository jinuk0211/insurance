import { NextRequest, NextResponse } from "next/server"
import { boundedInteger, isCatalogCronAuthorized, isCronAuthorized } from "@/lib/catalog/cron-auth"
import { runInsuranceCatalogCollection } from "@/lib/catalog/collector"
import { wasKbCatalogCollectedRecently } from "@/lib/catalog/repository"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"
export const maxDuration = 300

export async function GET(request: NextRequest) {
  const secret = process.env.CRON_SECRET
  const hasSecretAuthorization = isCronAuthorized(request.headers.get("authorization"), secret)
  if (!isCatalogCronAuthorized(
    request.headers.get("authorization"),
    secret,
    request.headers.get("user-agent"),
    process.env.VERCEL === "1",
  )) {
    return NextResponse.json({ error: "인증되지 않은 수집 요청입니다." }, { status: 401 })
  }

  try {
    if (!hasSecretAuthorization && await wasKbCatalogCollectedRecently(18)) {
      return NextResponse.json({ skipped: true, reason: "recently_collected" }, {
        headers: { "Cache-Control": "no-store" },
      })
    }
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
