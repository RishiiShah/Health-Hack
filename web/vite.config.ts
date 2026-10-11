import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// The backend has no CORS; in development Vite forwards API paths to it.
const api = process.env.API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  // Tailwind styles only the landing page (see src/landing.css).
  plugins: [tailwindcss()],
  esbuild: { jsx: "automatic" },
  server: {
    proxy: { "^/(auth|me|snapshot|events|gaps|offers|interventions|audit|admin|alerts|consults|schedule|ready|health)": api },
  },
});
