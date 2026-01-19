import type { NextConfig } from "next";
import { resolve } from "node:path";
import withFlowbiteReact from "flowbite-react/plugin/nextjs";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  // Static export for production (served by FastAPI)
  output: isDev ? undefined : "export",
  distDir: isDev ? ".next" : "out",

  // Set monorepo root to silence turbopack warning
  turbopack: {
    root: resolve(import.meta.dirname, "../.."),
  },

  // Allow dev origins for cross-origin requests
  allowedDevOrigins: ["localhost", "127.0.0.1"],

  // Rewrites only work in dev mode (proxies /api/* to FastAPI)
  ...(isDev && {
    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    },
  }),
};

export default withFlowbiteReact(nextConfig);
