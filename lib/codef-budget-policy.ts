const DEFAULT_CALL_LIMIT = 80
const ACCOUNT_CALL_QUOTA = 100

export function resolveCodefCallLimit(rawLimit: string | undefined): number {
  const limit = Number(rawLimit)
  return Number.isInteger(limit) && limit > 0 && limit <= ACCOUNT_CALL_QUOTA
    ? limit
    : DEFAULT_CALL_LIMIT
}

export function evaluateCodefCallBudget(
  used: number,
  limit: number,
): { allowed: boolean; remainingAfter: number } {
  if (used >= limit) return { allowed: false, remainingAfter: 0 }
  return { allowed: true, remainingAfter: limit - used - 1 }
}
