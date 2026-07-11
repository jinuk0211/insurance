export interface PreviewAuthEnvironment {
  isDeployed: boolean
  expectedUser: string | undefined
  expectedPassword: string | undefined
}

export type PreviewAuthDecision =
  | { allowed: true }
  | { allowed: false; status: 401 | 503 }

function constantTimeEqual(left: string, right: string): boolean {
  const length = Math.max(left.length, right.length)
  let difference = left.length ^ right.length

  for (let index = 0; index < length; index += 1) {
    difference |= (left.charCodeAt(index) || 0) ^ (right.charCodeAt(index) || 0)
  }

  return difference === 0
}

function decodeBasicCredentials(authorization: string): [string, string] | null {
  const match = authorization.match(/^Basic\s+([^\s]+)$/i)
  if (!match) return null

  try {
    const decoded = atob(match[1])
    const separator = decoded.indexOf(":")
    if (separator < 1) return null
    return [decoded.slice(0, separator), decoded.slice(separator + 1)]
  } catch {
    return null
  }
}

export function evaluatePreviewAuth(
  authorization: string | null,
  environment: PreviewAuthEnvironment,
): PreviewAuthDecision {
  const { isDeployed, expectedUser, expectedPassword } = environment

  if (!expectedUser || !expectedPassword) {
    return isDeployed ? { allowed: false, status: 503 } : { allowed: true }
  }

  const credentials = authorization ? decodeBasicCredentials(authorization) : null
  if (!credentials) return { allowed: false, status: 401 }

  const [user, password] = credentials
  const validUser = constantTimeEqual(user, expectedUser)
  const validPassword = constantTimeEqual(password, expectedPassword)

  return validUser && validPassword
    ? { allowed: true }
    : { allowed: false, status: 401 }
}
