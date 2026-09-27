/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingIncludes: { "/api/terms/ask": ["./lib/generated/qa-pages/*.json.gz"] },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
