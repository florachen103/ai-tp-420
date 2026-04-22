/** @type {import('next').NextConfig} */
const backend = (process.env.BACKEND_ORIGIN || "").trim().replace(/\/$/, "");

const nextConfig = {
  async rewrites() {
    const rules = [{ source: "/favicon.ico", destination: "/favicon.svg" }];
    if (backend) {
      rules.push({
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      });
    }
    return rules;
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
