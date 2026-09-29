/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingIncludes: { "/api/terms/ask": ["./lib/generated/qa-pages/*.json.gz"], "/api/terms/archive": ["./lib/generated/document-archive.json"] },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
