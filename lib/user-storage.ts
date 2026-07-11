/**
 * Client-side user storage for persistent login
 */

export interface SavedUser {
  name: string
  birth: string
  phone: string
  savedAt: number
}

const STORAGE_KEY = "kfinlegal_insurance_user"

export function getSavedUser(): SavedUser | null {
  if (typeof window === "undefined") return null

  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return null

    const parsed = JSON.parse(stored) as Record<string, unknown>
    if (
      typeof parsed.name !== "string" ||
      typeof parsed.birth !== "string" ||
      typeof parsed.phone !== "string" ||
      typeof parsed.savedAt !== "number"
    ) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }

    // Legacy versions stored CODEF credentials and resident-registration data
    // in localStorage. Keep only the non-secret fields needed to identify a
    // returning visitor and immediately overwrite the legacy payload.
    const user: SavedUser = {
      name: parsed.name,
      birth: parsed.birth,
      phone: parsed.phone,
      savedAt: parsed.savedAt,
    }

    // Check if data is older than 30 days
    const thirtyDays = 30 * 24 * 60 * 60 * 1000
    if (Date.now() - user.savedAt > thirtyDays) {
      localStorage.removeItem(STORAGE_KEY)
      return null
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    return user
  } catch {
    return null
  }
}

export function saveUser(user: Omit<SavedUser, "savedAt">): void {
  if (typeof window === "undefined") return

  const data: SavedUser = {
    ...user,
    savedAt: Date.now(),
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export function clearSavedUser(): void {
  if (typeof window === "undefined") return
  localStorage.removeItem(STORAGE_KEY)
}

export function maskPhone(phone: string): string {
  if (phone.length < 7) return phone
  return phone.slice(0, 3) + "****" + phone.slice(-4)
}

export function maskName(name: string): string {
  if (name.length <= 1) return name
  if (name.length === 2) return name[0] + "*"
  return name[0] + "*".repeat(name.length - 2) + name[name.length - 1]
}
