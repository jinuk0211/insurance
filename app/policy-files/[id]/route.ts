import policyLibrary from "@/lib/generated/official-policy-library.json"

// Vercel Edge returned different bytes for a pinned Hanwha PDF; Node served the verified original.
export const runtime = "nodejs"

interface RouteContext {
  params: Promise<{ id: string }>
}

async function proxyPolicy(request: Request, context: RouteContext, method: "GET" | "HEAD") {
  const { id } = await context.params
  const document = policyLibrary.documents.find((item) => item.id === id)
  if (!document) return new Response("약관을 찾을 수 없습니다.", { status: 404 })

  try {
    const expectedSha256 = document.expectedSha256
    if (!expectedSha256) {
      return new Response("원본 PDF 해시 확인이 필요합니다.", { status: 503 })
    }
    const upstream = await fetch(document.pdfUrl, { method })
    if (!upstream.ok || (method === "GET" && !upstream.body)) {
      return new Response("약관 PDF를 불러오지 못했습니다.", { status: 502 })
    }

    const headers = new Headers({
      "cache-control": "public, max-age=86400, s-maxage=604800",
      "content-disposition": `${new URL(request.url).searchParams.get("download") === "1" ? "attachment" : "inline"}; filename="${id}.pdf"`,
      "content-type": "application/pdf",
    })
    if (method === "GET") {
      const bytes = await upstream.arrayBuffer()
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
        .map((byte) => byte.toString(16).padStart(2, "0")).join("")
      if (hash !== expectedSha256) {
        return new Response("공식 PDF가 수집본과 달라 원문 표시를 중단했습니다.", { status: 502 })
      }
      headers.set("content-length", String(bytes.byteLength))
      let offset = 0
      const body = new ReadableStream<Uint8Array>({
        pull(controller) {
          if (offset >= bytes.byteLength) {
            controller.close()
            return
          }
          const length = Math.min(256 * 1024, bytes.byteLength - offset)
          controller.enqueue(new Uint8Array(bytes, offset, length))
          offset += length
        },
      })
      return new Response(body, { status: 200, headers })
    }
    for (const name of ["accept-ranges", "content-length", "content-range", "etag", "last-modified"]) {
      const value = upstream.headers.get(name)
      if (value) headers.set(name, value)
    }

    return new Response(null, {
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
