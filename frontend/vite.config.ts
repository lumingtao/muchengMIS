import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../mis_mvp/frontend_dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replace(/\\/g, "/");
          if (normalized.indexOf("/node_modules/") === -1) return undefined;
          if (normalized.indexOf("/react/") !== -1 || normalized.indexOf("/react-dom/") !== -1 || normalized.indexOf("/scheduler/") !== -1) return "react";
          if (normalized.indexOf("/@tanstack/react-query/") !== -1) return "query";

          if (/\/node_modules\/(rc-[^/]+|@rc-component\/)/.test(normalized) || normalized.indexOf("/node_modules/@ant-design/") !== -1) return "antd-rc";
          if (normalized.indexOf("/node_modules/antd/") !== -1) return "antd-core";
          return "vendor";
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8088",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/testSetup.ts",
  },
});
