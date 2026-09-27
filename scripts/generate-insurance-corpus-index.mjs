import { readFile, writeFile } from "node:fs/promises"
import { basename, join, resolve } from "node:path"

const sourceRoot = resolve(process.argv[2] ?? ".")
const output = resolve(process.argv[3] ?? "lib/generated/insurance-corpus-index.json")
const inventory = JSON.parse(await readFile(join(sourceRoot, "research/harness_v3/corpus_inventory_20260907_full_sources.json"), "utf8"))
const manifest = (await readFile(join(sourceRoot, "ECC_harness_v3_txt/data/raw/contracts/_collection_manifest.jsonl"), "utf8"))
  .trim().split("\n").map((line) => JSON.parse(line))
const sourceByHash = new Map(manifest.map((entry) => [entry.sha256, entry]))
const domain = inventory.domains.find((entry) => entry.domain === "kr_insurance")
if (!domain) throw new Error("KR insurance inventory missing")

const documents = domain.records
  .filter((record) => record.duplicate_of === null && record.mechanical_issues.length === 0)
  .map((record) => {
    const source = sourceByHash.get(record.sha256)
    const fileName = basename(record.path)
    const category = record.path.split("/")[4]
    return {
      id: record.sha256.slice(0, 16),
      sha256: record.sha256,
      category,
      fileName,
      bytes: record.bytes,
      title: source?.product_name?.trim() || fileName.replace(/\.pdf$/i, "").replaceAll("_", " "),
      source: source?.source ?? null,
      collectedAt: source?.collected_at ?? null,
      documentKind: source?.document_kind ?? null,
      url: source?.source_url ?? "https://fm1uaywjojumqwk2.public.blob.vercel-storage.com/ga-corpus/" + record.sha256 + ".pdf",
      provenance: source ? "recorded_source" : "local_copy_only",
    }
  })
  .sort((a, b) => a.category.localeCompare(b.category, "ko-KR") || a.fileName.localeCompare(b.fileName, "ko-KR"))

if (documents.length !== 1000) throw new Error("Expected 1000 screened unique PDFs, got " + documents.length)
if (documents.filter((item) => item.provenance === "recorded_source").length !== 644) throw new Error("Source manifest count changed")
if (new Set(documents.map((item) => item.sha256)).size !== documents.length) throw new Error("Duplicate hashes")

await writeFile(output, JSON.stringify({
  schemaVersion: 1,
  inventoryAt: inventory.generated_at,
  scope: "Byte-distinct, PDF-header-screened research collection; document types and contractual applicability are unverified.",
  documents,
}, null, 2) + "\n")
console.log("Wrote " + documents.length + " entries to " + output)
