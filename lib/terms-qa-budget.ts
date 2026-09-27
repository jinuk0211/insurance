import { createHmac } from "node:crypto"
import { BlobPreconditionFailedError, get, put } from "@vercel/blob"

export class QaBudgetExceeded extends Error {}
const clients = new Map<string, { used: number; expires: number }>()

export async function reserveDailyQuota(
  storage: Pick<typeof import("@vercel/blob"), "get" | "put"> = { get, put },
  now = Date.now(),
): Promise<void> {
  const day = new Date(now + 9 * 3600_000).toISOString().slice(0, 10)
  const pathname = "terms-qa-usage/" + day + ".json"
  const token = process.env.BLOB_READ_WRITE_TOKEN
  const abortSignal = AbortSignal.timeout(8000)
  for (let attempt = 0; attempt < 5; attempt++) {
    const current = await storage.get(pathname, { access: "public", token, useCache: false, abortSignal })
    if (current && (current.statusCode !== 200 || !current.stream || !current.blob.etag)) throw new Error("Invalid quota response")
    const state = current ? await new Response(current.stream).json() : { used: 0 }
    if (!Number.isInteger(state.used) || state.used < 0) throw new Error("Invalid quota state")
    if (state.used >= 300) throw new QaBudgetExceeded("Daily question limit reached")
    try {
      // Only the aggregate count is public; no questions, document IDs, or client identifiers.
      await storage.put(pathname, JSON.stringify({ used: state.used + 1 }), {
        access: "public", token, abortSignal, addRandomSuffix: false,
        allowOverwrite: Boolean(current), ifMatch: current?.blob.etag,
        contentType: "application/json", cacheControlMaxAge: 60,
      })
      return
    } catch (error) {
      // Another instance may have created or updated the same day's counter.
      if (current && !(error instanceof BlobPreconditionFailedError)) throw error
      if (attempt === 4) throw error
    }
  }
}

export async function reserveQaRequest(clientAddress: string): Promise<void> {
  if (!process.env.BLOB_READ_WRITE_TOKEN || !process.env.USER_KEY_SECRET) throw new Error("QA usage protection unavailable")
  const now = Date.now()
  for (const [key, value] of clients) if (value.expires <= now) clients.delete(key)
  const hash = createHmac("sha256", process.env.USER_KEY_SECRET).update(clientAddress).digest("hex").slice(0, 32)
  const bucket = clients.get(hash) || { used: 0, expires: now + 300_000 }
  if (bucket.used >= 10) throw new QaBudgetExceeded("Client question limit reached")
  if (clients.size >= 1000 && !clients.has(hash)) throw new QaBudgetExceeded("Question capacity reached")
  bucket.used++
  clients.set(hash, bucket)
  // The client throttle is per instance; the daily cap is shared across all deployments.
  await reserveDailyQuota()
}
