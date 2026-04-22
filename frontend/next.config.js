/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [{ source: "/favicon.ico", destination: "/favicon.svg" }];
  },
  reactStrictMode: true,
  experimental: {
    serverActions: { bodySizeLimit: "200mb" },
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "i.hd-r.cn",
        pathname: "/**",
      },
    ],
  },
};

module.exports = nextConfig;
