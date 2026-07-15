import { NextResponse, type NextRequest } from "next/server.js"
import { evaluatePreviewAuth } from "./lib/preview-auth.ts"

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
  const isInsuranceUi =
    request.nextUrl.pathname === "/insurance" ||
    request.nextUrl.pathname.startsWith("/insurance/")

  const isDemoOnly =
    process.env.INSURANCE_DEMO_ONLY === "true" ||
    !process.env.CODEF_CLIENT_ID ||
    !process.env.CODEF_CLIENT_SECRET ||
    !process.env.CODEF_PUBLIC_KEY

  if (isDemoOnly) {
    if (isInsuranceUi) {
      return applySecurityHeaders(NextResponse.next())
    }
    return applySecurityHeaders(
      NextResponse.json(
        { error: "실데이터 조회는 현재 비활성화되어 있습니다. 데모 모드를 이용해 주세요." },
        { status: 503 },
      ),
    )
  }

  const decision = evaluatePreviewAuth(request.headers.get("authorization"), {
    isDeployed: process.env.NODE_ENV === "production" || Boolean(process.env.VERCEL),
    expectedUser: process.env.INSURANCE_PREVIEW_USER,
    expectedPassword: process.env.INSURANCE_PREVIEW_PASSWORD,
  })

  if (!decision.allowed) {
    if (isInsuranceUi && decision.status === 401) {
      const response = new NextResponse("Live insurance access requires authorization.", {
        status: 401,
        headers: { "WWW-Authenticate": 'Basic realm="KFin Insurance", charset="UTF-8"' },
      })
      return applySecurityHeaders(response)
    }
    const response = NextResponse.json(
      {
        error:
          decision.status === 401
            ? "Live API authorization is required"
            : "Live API authorization is not configured",
      },
      { status: decision.status },
    )
    return applySecurityHeaders(response)
  }

  const requestHeaders = new Headers(request.headers)
  requestHeaders.delete("authorization")
  const response = NextResponse.next({ request: { headers: requestHeaders } })
  return applySecurityHeaders(response)
}

export const config = {
  matcher: ["/insurance/:path*", "/api/insurance/:path*"],
}
