/** Normalize CODEF auth-method values from API responses and client state. */
export function resolveCodefAuthMethod(value: unknown): "pass" | "sms" {
  return value === "0" || value === "sms" ? "sms" : "pass"
}

export const MAX_CODEF_CONFIRM_ATTEMPTS = 3

export function canAttemptCodefConfirmation(completedAttempts: number): boolean {
  return completedAttempts < MAX_CODEF_CONFIRM_ATTEMPTS
}

export type CodefRegistrationStartStep = "already_registered" | "captcha" | "sms_or_pass" | "error"

export interface CodefRegistrationStartOutcome {
  step: CodefRegistrationStartStep
  code: string | null
  message: string
}

function asRecord(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" ? value as Record<string, unknown> : {}
}

/** Only show an authentication wait screen when CODEF returned a valid two-way session. */
export function classifyCodefRegistrationStart(value: unknown): CodefRegistrationStartOutcome {
  const response = asRecord(value)
  const result = asRecord(response.result)
  const data = asRecord(response.data)
  const extraInfo = asRecord(data.extraInfo)
  const code = typeof result.code === "string" ? result.code : null
  const message = typeof result.message === "string" ? result.message : ""

  if (code === "CF-12069") {
    return { step: "already_registered", code, message }
  }

  if (code !== "CF-03002" && code !== "CF-03003") {
    return {
      step: "error",
      code,
      message: message || "CODEF 회원 확인 요청에 실패했습니다.",
    }
  }

  if (typeof data.jti !== "string" || !data.jti.trim()) {
    return {
      step: "error",
      code,
      message: "CODEF 인증 세션이 생성되지 않았습니다. 잠시 후 다시 시도해주세요.",
    }
  }

  const secureNo = typeof extraInfo.reqSecureNo === "string" ? extraInfo.reqSecureNo : ""
  return {
    step: secureNo.length > 10 ? "captcha" : "sms_or_pass",
    code,
    message,
  }
}

export function resolveRegistrationStartUiAction(step: unknown): "query" | "captcha" | "auth" | "error" {
  if (step === "already_registered") return "query"
  if (step === "captcha") return "captcha"
  if (step === "sms_or_pass") return "auth"
  return "error"
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
