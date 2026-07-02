import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/admin": "http://127.0.0.1:8001",
      "/auth": "http://127.0.0.1:8001",
      "/uploads": "http://127.0.0.1:8001",
    },
  },
});
