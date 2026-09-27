import policyLibrary from "@/lib/generated/official-policy-library.json"

export const runtime = "edge"

interface RouteContext {
  params: Promise<{ id: string }>
}

async function proxyPolicy(request: Request, context: RouteContext, method: "GET" | "HEAD") {
  const { id } = await context.params
  const document = policyLibrary.documents.find((item) => item.id === id)
  if (!document) return new Response("약관을 찾을 수 없습니다.", { status: 404 })

  try {
    const range = request.headers.get("range")
    const expectedSha256 = "expectedSha256" in document ? document.expectedSha256 : null
    const upstream = await fetch(document.pdfUrl, {
      method,
      headers: range && !expectedSha256 ? { range } : undefined,
    })
    if (!upstream.ok || (method === "GET" && !upstream.body)) {
      return new Response("약관 PDF를 불러오지 못했습니다.", { status: 502 })
    }

    const headers = new Headers({
      "cache-control": "public, max-age=86400, s-maxage=604800",
      "content-disposition": 'inline; filename="' + id + '.pdf"',
      "content-type": "application/pdf",
    })
    if (expectedSha256 && method === "GET") {
      const bytes = await upstream.arrayBuffer()
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
        .map((byte) => byte.toString(16).padStart(2, "0")).join("")
      if (hash !== expectedSha256) {
        return new Response("공식 PDF가 수집본과 달라 원문 표시를 중단했습니다.", { status: 502 })
      }
      headers.set("content-length", String(bytes.byteLength))
      return new Response(bytes, { status: 200, headers })
    }
    for (const name of ["accept-ranges", "content-length", "content-range", "etag", "last-modified"]) {
      const value = upstream.headers.get(name)
      if (value) headers.set(name, value)
    }

    return new Response(method === "HEAD" ? null : upstream.body, {
      status: upstream.status,
      headers,
    })
  } catch {
    return new Response("약관 PDF를 불러오지 못했습니다.", { status: 502 })
  }
}

export function GET(request: Request, context: RouteContext) {
  return proxyPolicy(request, context, "GET")
}

export function HEAD(request: Request, context: RouteContext) {
  return proxyPolicy(request, context, "HEAD")
}
