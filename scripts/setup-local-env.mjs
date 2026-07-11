import { randomBytes } from "node:crypto"
import { existsSync, readFileSync, writeFileSync } from "node:fs"
import { resolve } from "node:path"

const targetPath = resolve(".env.local")

let contents = existsSync(targetPath)
  ? readFileSync(targetPath, "utf8")
  : "# Local development secrets. Do not commit.\n"

const generated = []

function fillSecret(name) {
  const pattern = new RegExp(`^${name}=(.*)$`, "m")
  const match = contents.match(pattern)

  if (match?.[1].trim()) return

  const value = randomBytes(32).toString("base64")
  contents = match
    ? contents.replace(pattern, `${name}=${value}`)
    : `${contents.trimEnd()}\n${name}=${value}\n`
  generated.push(name)
}

fillSecret("HISTORY_ENC_KEY")
fillSecret("USER_KEY_SECRET")

writeFileSync(targetPath, contents, { encoding: "utf8", mode: 0o600 })

if (generated.length) {
  console.log(`Generated ${generated.join(" and ")} in .env.local.`)
} else {
  console.log("Local encryption secrets are already configured.")
}
