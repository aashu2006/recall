import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Keeps the dev badge out of demo recordings.
  devIndicators: false,
};

export default nextConfig;
