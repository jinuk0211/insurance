/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: "/policy-files/:fileName",
        destination: "https://www.kbinsure.co.kr/CG802030003.ec?fileNm=:fileName",
      },
    ]
  },
}

export default nextConfig
