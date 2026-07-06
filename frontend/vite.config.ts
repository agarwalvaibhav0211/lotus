import { defineConfig, splitVendorChunkPlugin } from "vite";
import react from "@vitejs/plugin-react";
import vitePluginImp from "vite-plugin-imp";
import tsconfigPaths from "vite-tsconfig-paths";

// Django's actual API/app/admin routes never end in a source-file extension,
// but requests for frontend modules under those same path prefixes (e.g.
// src/api/api.ts served as /api/api.ts) do. Skip proxying those so Vite can
// serve its own source files instead of Django swallowing them.
function bypassSourceRequests(req: import("http").IncomingMessage) {
  const path = (req.url || "").split("?")[0];
  if (/\.(ts|tsx|js|jsx|css|less|scss|json|svg|png|jpg|jpeg|gif|ico)$/.test(path)) {
    return path;
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  build: {
    manifest: true,
    // outDir: "../static/dist",
    // emptyOutDir: true,
    // rollupOptions: {
    //   input: {
    //     main: "./src/index.html",
    //   },
    //   output: {
    //     chunkFileNames: undefined,
    //   },
    // },
  },
  base: process.env.mode === "production" ? "/static/" : "./",
  publicDir: "./public",
  root: "./src",
  resolve: {
    alias: [{ find: /^~/, replacement: "" }],
  },
  plugins: [react(), splitVendorChunkPlugin(), tsconfigPaths()],
  server: {
    host: true,
    hmr: {
      clientPort: 443,
      protocol: "wss",
      host: "lotus.oracle.makemybazar.com",
    },
    port: 3000,
    open: false,
    middlewareMode: false,
    strictPort: true,
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api/track": {
        target: "http://lotus-event-ingestion:7998",
        changeOrigin: true,
        bypass: bypassSourceRequests,
      },
      "/api": {
        target: "http://lotus-backend:8000",
        changeOrigin: true,
        bypass: bypassSourceRequests,
      },
      "/app": {
        target: "http://lotus-backend:8000",
        changeOrigin: true,
        bypass: bypassSourceRequests,
      },
      "/admin": {
        target: "http://lotus-backend:8000",
        changeOrigin: true,
        bypass: bypassSourceRequests,
      },
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
      },
    },
  },
});
