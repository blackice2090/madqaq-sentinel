import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The web app lives inside the Python repository; pin the workspace root to this folder.
  turbopack: { root: path.resolve(".") },
};

export default nextConfig;
