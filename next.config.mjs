import { readFileSync } from "node:fs"

const policyLibrary = JSON.parse(
  readFileSync(new URL("./lib/generated/official-policy-library.json", import.meta.url), "utf8"),
)

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return policyLibrary.documents.map((document) => ({
      source: `/policy-files/${document.id}`,
      destination: document.pdfUrl,
    }))
  },
}

export default nextConfig
