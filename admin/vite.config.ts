import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/admin": "http://127.0.0.1:8001",
      "/auth": "http://127.0.0.1:8001",
    },
  },
});
