interface RobotsGroup {
  agents: string[]
  rules: Array<{ directive: "allow" | "disallow"; path: string }>
}

export function isPathAllowedByRobots(
  robotsText: string,
  targetUrl: string,
  userAgent: string,
): boolean {
  const groups = parseRobots(robotsText)
  const agent = userAgent.toLocaleLowerCase()
  const exact = groups.filter((group) => group.agents.some((value) => value !== "*" && agent.includes(value)))
  const applicable = exact.length > 0
    ? exact
    : groups.filter((group) => group.agents.includes("*"))
  if (applicable.length === 0) return true

  const path = new URL(targetUrl).pathname
  const rules = applicable.flatMap((group) => group.rules)
    .filter((rule) => rule.path && path.startsWith(rule.path))
    .sort((left, right) => right.path.length - left.path.length)
  if (rules.length === 0) return true
  return rules[0].directive === "allow"
}

function parseRobots(text: string): RobotsGroup[] {
  const groups: RobotsGroup[] = []
  let current: RobotsGroup | null = null
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*$/, "").trim()
    if (!line) continue
    const separator = line.indexOf(":")
    if (separator < 0) continue
    const key = line.slice(0, separator).trim().toLocaleLowerCase()
    const value = line.slice(separator + 1).trim()
    if (key === "user-agent") {
      if (!current || current.rules.length > 0) {
        current = { agents: [], rules: [] }
        groups.push(current)
      }
      current.agents.push(value.toLocaleLowerCase())
      continue
    }
    if (!current || (key !== "allow" && key !== "disallow")) continue
    current.rules.push({ directive: key, path: value })
  }
  return groups
}
