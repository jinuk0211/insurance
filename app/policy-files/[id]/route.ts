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
    const upstream = await fetch(document.pdfUrl, {
      method,
      headers: range ? { range } : undefined,
    })
    if (!upstream.ok || (method === "GET" && !upstream.body)) {
      return new Response("약관 PDF를 불러오지 못했습니다.", { status: 502 })
    }

    const headers = new Headers({
      "cache-control": "public, max-age=86400, s-maxage=604800",
      "content-disposition": 'inline; filename="' + id + '.pdf"',
      "content-type": "application/pdf",
    })
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
