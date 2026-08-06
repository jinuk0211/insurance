const SOURCE_URL = "https://www.kbinsure.co.kr/CG802030003.ec?fileNm=25303_1_1%28%B0%A3%C6%ED%29.pdf"

export const runtime = "edge"

async function proxyPolicy(request: Request, method: "GET" | "HEAD") {
  const range = request.headers.get("range")
  const upstream = await fetch(SOURCE_URL, {
    method,
    headers: range ? { range } : undefined,
  })

  if (!upstream.ok || (method === "GET" && !upstream.body)) {
    return new Response("약관 PDF를 불러오지 못했습니다.", { status: 502 })
  }

  const headers = new Headers({
    "accept-ranges": upstream.headers.get("accept-ranges") ?? "bytes",
    "cache-control": "public, max-age=86400, s-maxage=604800",
    "content-disposition": 'inline; filename="25303_1_1.pdf"',
    "content-type": "application/pdf",
  })
  for (const name of ["content-length", "content-range", "etag", "last-modified"]) {
    const value = upstream.headers.get(name)
    if (value) headers.set(name, value)
  }

  return new Response(method === "HEAD" ? null : upstream.body, {
    status: upstream.status,
    headers,
  })
}

export async function GET(request: Request) {
  return proxyPolicy(request, "GET")
}

export async function HEAD(request: Request) {
  return proxyPolicy(request, "HEAD")
}
