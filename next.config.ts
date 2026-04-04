import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["proper-lockfile"],
  async rewrites() {
    return [
      {
        source: "/api/ai/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
