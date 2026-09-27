import { NextResponse, type NextRequest } from "next/server.js"

const SECURITY_HEADERS = {
  "Cache-Control": "private, no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
} as const

function applySecurityHeaders(response: NextResponse): NextResponse {
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(name, value)
  }
  return response
}

export function proxy(request: NextRequest): NextResponse {
  const isPublicUi =
    request.nextUrl.pathname === "/insurance" ||
    request.nextUrl.pathname.startsWith("/insurance/") ||
    request.nextUrl.pathname === "/pension" ||
    request.nextUrl.pathname.startsWith("/pension/")

  if (isPublicUi) {
    return applySecurityHeaders(NextResponse.next())
  }

  // Deployed live APIs stay closed until GA advisor auth and per-customer access checks exist.
  const localLiveTest =
    process.env.NODE_ENV === "development" &&
    process.env.VERCEL !== "1" &&
    process.env.INSURANCE_LOCAL_LIVE_TEST === "true" &&
    process.env.INSURANCE_DEMO_ONLY !== "true" &&
    Boolean(process.env.CODEF_CLIENT_ID && process.env.CODEF_CLIENT_SECRET && process.env.CODEF_PUBLIC_KEY)
  if (!localLiveTest) {
    return applySecurityHeaders(
      NextResponse.json(
        { error: "실데이터 조회는 GA 접근 인증이 준비될 때까지 비활성화되어 있습니다. 합성 데모를 이용해 주세요." },
        { status: 503 },
      ),
    )
  }

  const requestHeaders = new Headers(request.headers)
  requestHeaders.delete("authorization")
  const response = NextResponse.next({ request: { headers: requestHeaders } })
  return applySecurityHeaders(response)
}

export const config = {
  matcher: [
    "/insurance/:path*",
    "/pension/:path*",
    "/api/insurance/:path*",
    "/api/codef-datasets/:path*",
  ],
}
