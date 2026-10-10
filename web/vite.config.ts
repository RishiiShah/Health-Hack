import { defineConfig } from "vite";

// The backend has no CORS; in development Vite forwards API paths to it.
const api = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  server: {
    proxy: { "^/(snapshot|events|gaps|offers|interventions|audit|admin|alerts|consults|ready|health)": api },
  },
});
