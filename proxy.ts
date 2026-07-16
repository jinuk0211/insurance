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

  const isDemoOnly =
    process.env.INSURANCE_DEMO_ONLY === "true" ||
    !process.env.CODEF_CLIENT_ID ||
    !process.env.CODEF_CLIENT_SECRET ||
    !process.env.CODEF_PUBLIC_KEY

  if (isPublicUi) {
    return applySecurityHeaders(NextResponse.next())
  }

  if (isDemoOnly) {
    return applySecurityHeaders(
      NextResponse.json(
        { error: "실데이터 조회는 현재 비활성화되어 있습니다. 데모 모드를 이용해 주세요." },
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
