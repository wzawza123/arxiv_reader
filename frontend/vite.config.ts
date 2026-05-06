import { defineConfig, loadEnv, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

const DEFAULT_ALLOWED_HOSTS = ["4kf5821882.qicp.vip", "189h5p7535.51mypc.cn"];

function splitCsv(value: string | undefined): string[] {
  return value
    ? value
        .split(",")
        .map((item) => item.trim())
        .map((item) => {
          try {
            return new URL(item.includes("://") ? item : `http://${item}`).host;
          } catch {
            return item;
          }
        })
        .filter(Boolean)
    : [];
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendUrl = env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
  const envAllowedHosts = splitCsv(env.VITE_ALLOWED_HOSTS);
  const allowedHosts = Array.from(new Set([...DEFAULT_ALLOWED_HOSTS, ...envAllowedHosts]));

  const makeProxy = (): ProxyOptions => ({
    target: backendUrl,
    changeOrigin: true,
    secure: false,
    proxyTimeout: 120_000,
    timeout: 120_000,
  });

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      allowedHosts,
      proxy: {
        "/api": makeProxy(),
        "/figures": makeProxy(),
      },
    },
  };
});
