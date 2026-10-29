import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite"; /* instead of @tailwindcss/postcss */
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath, URL } from "node:url";

// https://vitejs.dev/config/
export default defineConfig({
  base: "/static/", // base path to serve static assets
  build: {
    outDir: "./dist",
    manifest: "manifest.json",
    rollupOptions: {
      input: {
        main: "/src/js/main.js",
      },
    },
  },
  server: {
    host: "localhost",
    port: 5173,
    // Emit full URLs (e.g. fonts) in dev assets so they resolve against the
    // Vite dev server, not the Django origin where the page is served.
    // Keep in sync with DJANGO_VITE.dev_server_port in config/settings/base.py.
    // https://github.com/MrBin99/django-vite/issues/167
    origin: process.env.VITE_DEV_SERVER_URL || "http://localhost:5173",
    cors: true,
  },
  resolve: {
    alias: {
      $lib: fileURLToPath(new URL("./src/js/svelte/library", import.meta.url)),
    },
  },
  plugins: [
    tailwindcss(),
    svelte({
      configFile: false,
      compilerOptions: {
        dev: process.env.NODE_ENV !== "production",
      },
    }),
  ],
});
