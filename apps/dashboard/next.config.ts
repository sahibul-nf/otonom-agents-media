import path from "node:path";
import {fileURLToPath} from "node:url";
import type {NextConfig} from "next";

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Monorepo/worktree: stop Turbopack from inferring root at src/app (missing next package).
  turbopack: {
    root: dashboardRoot,
  },
};

export default nextConfig;
