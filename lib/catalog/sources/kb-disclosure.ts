import { load } from "cheerio"
import { isPathAllowedByRobots } from "../robots.ts"
import {
  type CatalogCursor,
  type CatalogDocumentCandidate,
  type CatalogDocumentKind,
  type CatalogPageResult,
  type CatalogProductListing,
  type CatalogProductVersionCandidate,
  normalizeDisclosureDate,
  stableFingerprint,
} from "../types.ts"

const BASE_URL = "https://www.kbinsure.co.kr"
const LIST_URL = `${BASE_URL}/CG802030001.ec`
const DETAIL_URL = `${BASE_URL}/CG802030002.ec`
const ROBOTS_URL = `${BASE_URL}/robots.txt`
const PAGE_SIZE = 10
const DEFAULT_USER_AGENT = "KFinLegalCatalogBot/1.0 (+https://insurance-eta-gray.vercel.app)"

interface FetchResponse {
  ok: boolean
  status: number
  headers: Headers
  text(): Promise<string>
  arrayBuffer(): Promise<ArrayBuffer>
}

type Fetcher = (input: string | URL, init?: RequestInit) => Promise<FetchResponse>

export interface KbCollectorOptions {
  maxProducts: number
  fetcher?: Fetcher
  delay?: (milliseconds: number) => Promise<void>
  userAgent?: string
}

export function parseKbProductList(html: string): CatalogProductListing[] {
  const $ = load(html)
  const products: CatalogProductListing[] = []
  $("table.tb_list > tbody > tr").each((_, row) => {
    const cells = $(row).children("td")
    const anchor = $(row).find("a[href*='detail']").first()
    const handler = `${anchor.attr("href") ?? ""} ${anchor.attr("onclick") ?? ""}`
    const match = handler.match(/detail\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)/)
    if (!match || cells.length < 4) return
    const statusText = $(cells[0]).text().replace(/\s+/g, " ").trim()
    products.push({
      externalProductCode: match[1],
      name: anchor.text().replace(/\s+/g, " ").trim(),
      productType: $(cells[1]).text().replace(/\s+/g, " ").trim() || null,
      saleStatus: /판매중/.test(statusText) ? "on_sale" : /판매종료|판매중지/.test(statusText) ? "off_sale" : "unknown",
      detailGroup: match[2],
      detailSequence: match[3],
    })
  })
  return products
}

export function parseKbProductVersions(
  html: string,
  listing: CatalogProductListing,
): CatalogProductVersionCandidate[] {
  const $ = load(html)
  const versions: CatalogProductVersionCandidate[] = []
  $("table.tb_default04 > tbody > tr").each((rowIndex, row) => {
    const cells = $(row).children("td")
    if (cells.length < 4) return
    const effectiveFrom = normalizeDisclosureDate($(cells[0]).text())
    const effectiveTo = normalizeDisclosureDate($(cells[1]).text())
    if (!effectiveFrom && !effectiveTo) return
    const documents: CatalogDocumentCandidate[] = []
    $(row).find("a[href]").each((anchorIndex, anchor) => {
      const href = $(anchor).attr("href")
      if (!href) return
      const label = `${$(anchor).text()} ${$(anchor).find("img").attr("alt") ?? ""}`.trim()
      const kind = documentKind(label, anchorIndex)
      const url = new URL(href, BASE_URL).toString()
      documents.push({
        kind,
        url,
        fileName: new URL(url).searchParams.get("fileNm"),
      })
    })
    const uniqueDocuments = Array.from(new Map(documents.map((document) => [document.url, document])).values())
    const versionKey = effectiveFrom ?? effectiveTo ?? `row-${rowIndex + 1}`
    const value = {
      versionKey,
      effectiveFrom,
      effectiveTo,
      saleStatus: listing.saleStatus,
      documents: uniqueDocuments,
    } satisfies Omit<CatalogProductVersionCandidate, "fingerprint">
    versions.push({ ...value, fingerprint: stableFingerprint(value) })
  })
  return versions
}

function documentKind(label: string, anchorIndex: number): CatalogDocumentKind {
  if (/약관/.test(label)) return "terms"
  if (/사업방법/.test(label)) return "business_method"
  if (/상품요약/.test(label)) return "product_summary"
  return (["terms", "business_method", "product_summary"] as const)[anchorIndex] ?? "description"
}

export async function collectKbDisclosurePage(
  cursor: CatalogCursor,
  options: KbCollectorOptions,
): Promise<CatalogPageResult> {
  const fetcher = options.fetcher ?? (globalThis.fetch as unknown as Fetcher)
  const userAgent = options.userAgent ?? process.env.CATALOG_CRAWLER_USER_AGENT ?? DEFAULT_USER_AGENT
  const delay = options.delay ?? ((milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)))
  const robots = await fetcher(ROBOTS_URL, { headers: { "User-Agent": userAgent } })
  if (robots.ok && !isPathAllowedByRobots(await robots.text(), LIST_URL, userAgent)) {
    throw new Error("KB손해보험 robots.txt가 상품공시 수집을 허용하지 않습니다.")
  }

  const session = await createSession(fetcher, userAgent)
  const listResponse = await session(LIST_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      devonTargetRow: String(cursor.targetRow),
      devonOrderBy: "",
      gubun: cursor.category,
      goodsNm: "",
      onsaleYn: cursor.saleFilter,
      bojongNo: "",
      bojongSeq: "",
      search_onsale_yn: cursor.saleFilter,
      search_bojong_no: "",
      search_gubun: cursor.category,
      search_goods_nm: "",
    }),
  })
  if (!listResponse.ok) throw new Error(`KB손해보험 상품 목록 조회 실패 (${listResponse.status})`)
  const allListings = parseKbProductList(await decodeHtml(listResponse))
  const listings = allListings.slice(0, Math.max(1, Math.min(options.maxProducts, PAGE_SIZE)))
  const products = []
  for (const [index, listing] of listings.entries()) {
    if (index > 0) await delay(250)
    const detailResponse = await session(DETAIL_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        bojongNo: listing.externalProductCode,
        gubun: listing.detailGroup,
        bojongSeq: listing.detailSequence,
      }),
    })
    if (!detailResponse.ok) throw new Error(`KB손해보험 상품 상세 조회 실패 (${detailResponse.status})`)
    products.push({ listing, versions: parseKbProductVersions(await decodeHtml(detailResponse), listing) })
  }

  if (listings.length < allListings.length) {
    return {
      products,
      nextCursor: { ...cursor, targetRow: cursor.targetRow + listings.length },
      cycleCompleted: false,
    }
  }
  const pageCompleted = allListings.length < PAGE_SIZE
  if (!pageCompleted) {
    return {
      products,
      nextCursor: { ...cursor, targetRow: cursor.targetRow + PAGE_SIZE },
      cycleCompleted: false,
    }
  }
  if (cursor.saleFilter === "Y") {
    return {
      products,
      nextCursor: { ...cursor, targetRow: 1, saleFilter: "N" },
      cycleCompleted: false,
    }
  }
  return {
    products,
    nextCursor: { ...cursor, targetRow: 1, saleFilter: "Y" },
    cycleCompleted: true,
  }
}

async function createSession(fetcher: Fetcher, userAgent: string) {
  let cookie = ""
  const initial = await fetcher(LIST_URL, { headers: { "User-Agent": userAgent } })
  if (!initial.ok) throw new Error(`KB손해보험 상품공시 접속 실패 (${initial.status})`)
  cookie = readCookies(initial.headers)
  return async (url: string, init: RequestInit): Promise<FetchResponse> => {
    const headers = new Headers(init.headers)
    headers.set("User-Agent", userAgent)
    headers.set("Referer", LIST_URL)
    if (cookie) headers.set("Cookie", cookie)
    const response = await fetcher(url, { ...init, headers })
    const nextCookies = readCookies(response.headers)
    if (nextCookies) cookie = nextCookies
    return response
  }
}

function readCookies(headers: Headers): string {
  const values = typeof headers.getSetCookie === "function"
    ? headers.getSetCookie()
    : [headers.get("set-cookie") ?? ""]
  return values
    .filter(Boolean)
    .map((value) => value.split(";", 1)[0])
    .join("; ")
}

async function decodeHtml(response: FetchResponse): Promise<string> {
  const contentType = response.headers.get("content-type")?.toLocaleLowerCase() ?? ""
  if (contentType.includes("charset=euc-kr") || contentType.includes("charset=ks_c_5601-1987")) {
    return new TextDecoder("euc-kr").decode(await response.arrayBuffer())
  }
  return response.text()
}
