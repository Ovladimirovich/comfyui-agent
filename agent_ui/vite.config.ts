import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev-server. Прокси к Agent Core (app/ui.py) на 127.0.0.1:8189,
// чтобы frontend обращался к относительным путям (/turn, /events, /api/*).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/turn": "http://127.0.0.1:8189",
      "/events": "http://127.0.0.1:8189",
      "/api": "http://127.0.0.1:8189",
      "/asset": "http://127.0.0.1:8189",
    },
  },
});