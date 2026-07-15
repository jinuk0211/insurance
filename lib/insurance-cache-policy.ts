const DEFAULT_CACHE_TTL_HOURS = 24
const MAX_CACHE_TTL_HOURS = 24 * 30

export function getInsuranceCacheTtlMs(rawHours: string | undefined): number {
  const hours = Number(rawHours)
  const normalized = Number.isInteger(hours) && hours > 0 && hours <= MAX_CACHE_TTL_HOURS
    ? hours
    : DEFAULT_CACHE_TTL_HOURS
  return normalized * 60 * 60 * 1000
}

export function isInsuranceCacheFresh(
  queriedAt: Date,
  now: Date,
  ttlMs: number,
): boolean {
  return queriedAt.getTime() > now.getTime() - ttlMs
}
