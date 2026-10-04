export default defineNuxtConfig({
  ssr: false,
  telemetry: false,
  devtools: { enabled: false },
  compatibilityDate: "2026-10-01",
  app: {
    // Built assets are served by FastAPI under /_assets (see backend/app/main.py).
    buildAssetsDir: "/_assets/",
    head: {
      title: "Clinique Dentaire",
      htmlAttrs: { lang: "fr", dir: "ltr" },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
      ],
    },
  },
  css: [
    "@fontsource/inter/400.css",
    "@fontsource/inter/500.css",
    "@fontsource/inter/600.css",
    "@fontsource/inter/700.css",
    "@fontsource/noto-sans-arabic/400.css",
    "@fontsource/noto-sans-arabic/500.css",
    "@fontsource/noto-sans-arabic/600.css",
    "@fontsource/noto-sans-arabic/700.css",
    "~/assets/css/main.css",
  ],
  vite: {
    server: {
      proxy: {
        "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      },
    },
  },
  typescript: { strict: true },
})
