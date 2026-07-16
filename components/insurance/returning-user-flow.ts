export type ReturningUserCheckOutcome =
  | { action: "query"; sessionId: string }
  | { action: "reconnect" }

interface ReturningUserCheckResponse {
  found?: unknown
  sessionId?: unknown
}

export function resolveReturningUserCheck(
  response: ReturningUserCheckResponse,
): ReturningUserCheckOutcome {
  if (
    response.found === true
    && typeof response.sessionId === "string"
    && response.sessionId.length > 0
  ) {
    return { action: "query", sessionId: response.sessionId }
  }
  return { action: "reconnect" }
}
