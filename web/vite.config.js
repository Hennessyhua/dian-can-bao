import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    target: ["es2018", "safari13"],
    cssTarget: "safari13",
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: ["terminal.local"],
  },
});
