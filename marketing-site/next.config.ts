import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Pin the workspace root explicitly — a stray package-lock.json at
  // /Users/paulmoga (unrelated to this project) confuses Turbopack's
  // auto-detected root, which then tries to scan the whole home directory
  // and hits a macOS permission wall.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
