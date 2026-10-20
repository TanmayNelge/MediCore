import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// FIX: @tailwindcss/vite plugin was missing. Without it, Tailwind v4's
// @import "tailwindcss" directive in index.css is not processed, meaning
// ALL utility classes (bg-accent, text-ink-muted, etc.) produce no CSS
// and the entire UI renders unstyled.
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
