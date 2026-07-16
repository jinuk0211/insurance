import { timingSafeEqual } from "node:crypto"

export function isCronAuthorized(authorization: string | null, secret: string | undefined): boolean {
  if (!secret || !authorization?.startsWith("Bearer ")) return false
  const supplied = Buffer.from(authorization.slice("Bearer ".length))
  const expected = Buffer.from(secret)
  return supplied.length === expected.length && timingSafeEqual(supplied, expected)
}

export function isCatalogCronAuthorized(
  authorization: string | null,
  secret: string | undefined,
  userAgent: string | null,
  isVercelDeployment: boolean,
): boolean {
  if (secret) return isCronAuthorized(authorization, secret)
  return isVercelDeployment && userAgent === "vercel-cron/1.0"
}

export function boundedInteger(value: string | undefined, fallback: number, min: number, max: number): number {
  const parsed = Number(value)
  if (!Number.isInteger(parsed)) return fallback
  return Math.max(min, Math.min(max, parsed))
}
