import { readFileSync } from "node:fs"
import { join } from "node:path"
import { type ArchiveCatalog, searchArchive } from "@/lib/document-archive"

export const runtime = "nodejs"
let catalog: ArchiveCatalog | undefined
export function GET(request: Request) {
  catalog ??= JSON.parse(readFileSync(join(process.cwd(), "lib/generated/document-archive.json"), "utf8")) as ArchiveCatalog
  return Response.json(searchArchive(catalog, new URL(request.url).searchParams), {
    headers: { "Cache-Control": "public, max-age=60, s-maxage=300" },
  })
}
