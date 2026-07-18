import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["hermes-icon.svg"],
      manifest: {
        name: "Hermes Subscription Manager",
        short_name: "Hermes",
        description: "Self-hosted subscription lifecycle manager",
        theme_color: "#176b61",
        background_color: "#f3f6f4",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/hermes-icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" },
        ],
      },
      workbox: { navigateFallback: "/index.html", runtimeCaching: [] },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
