import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/ai/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
      {
        source: "/api/extension/:path*",
        destination: "http://localhost:8000/api/extension/:path*",
      },
    ];
  },
};

export default nextConfig;
