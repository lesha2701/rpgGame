/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

const backendProxy = {
  "/api": {
    target: "http://localhost:8100",
    changeOrigin: true,
  },
  "/static": {
    target: "http://localhost:8100",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5174,
    proxy: backendProxy,
  },
  preview: {
    host: true,
    port: 5174,
    proxy: backendProxy,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
