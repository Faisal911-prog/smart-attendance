import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the browser talks to the Vite server only; requests to /api
// are forwarded to Django. This avoids CORS problems and lets a tunnel
// (ngrok / Cloudflare Tunnel) expose a single https address to phones.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
