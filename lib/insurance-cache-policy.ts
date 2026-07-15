const MAX_CACHE_TTL_HOURS = 24 * 30

export function getInsuranceCacheTtlMs(rawHours: string | undefined): number {
  const hours = Number(rawHours)
  if (rawHours !== undefined && Number.isInteger(hours) && hours > 0 && hours <= MAX_CACHE_TTL_HOURS) {
    return hours * 60 * 60 * 1000
  }
  return 0
}

export function isInsuranceCacheFresh(
  queriedAt: Date,
  now: Date,
  ttlMs: number,
): boolean {
  if (ttlMs <= 0) return true
  return queriedAt.getTime() > now.getTime() - ttlMs
}
