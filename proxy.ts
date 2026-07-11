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
  const decision = evaluatePreviewAuth(request.headers.get("authorization"), {
    isDeployed: Boolean(process.env.VERCEL),
    expectedUser: process.env.INSURANCE_PREVIEW_USER,
    expectedPassword: process.env.INSURANCE_PREVIEW_PASSWORD,
  })

  if (!decision.allowed) {
    const isChallenge = decision.status === 401
    const response = new NextResponse(
      isChallenge ? "Authentication required" : "Preview access is not configured",
      { status: decision.status },
    )
    if (isChallenge) {
      response.headers.set(
        "WWW-Authenticate",
        'Basic realm="KFin Insurance Preview", charset="UTF-8"',
      )
    }
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
