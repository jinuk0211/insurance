/** Normalize CODEF auth-method values from API responses and client state. */
export function resolveCodefAuthMethod(value: unknown): "pass" | "sms" {
  return value === "0" || value === "sms" ? "sms" : "pass"
}

export const MAX_CODEF_CONFIRM_ATTEMPTS = 3

export function canAttemptCodefConfirmation(completedAttempts: number): boolean {
  return completedAttempts < MAX_CODEF_CONFIRM_ATTEMPTS
}

/** Accept only complete image data URLs or raw base64 CAPTCHA payloads. */
export function toCaptchaImageSrc(value: unknown): string | null {
  if (typeof value !== "string") return null

  const trimmed = value.trim()
  if (!trimmed) return null
  if (/^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/=\s]+$/i.test(trimmed)) {
    return trimmed
  }

  const base64 = trimmed.replace(/\s/g, "")
  if (!/^[a-z0-9+/]+={0,2}$/i.test(base64)) return null
  return `data:image/png;base64,${base64}`
}
