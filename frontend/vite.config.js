import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import process from 'node:process'

const DJANGO_ORIGIN = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react()],

  // Assets stay at the root so one build runs unchanged under the dev server,
  // `vite preview`, and Django (which serves this directory via WHITENOISE_ROOT).
  base: '/',

  server: {
    host: true, // equivalent to 0.0.0.0
    port: Number(process.env.PORT) || 5173,
    // Lets the app call '/api/...' in development exactly as it does in
    // production, so no environment-specific base URL is needed.
    proxy: { '/api': DJANGO_ORIGIN },
  },

  preview: {
    // Allow the host Render reported as blocked
    allowedHosts: ['yannzakpa.space'],
    // Bind to all interfaces so Render can detect the open port
    host: '0.0.0.0',
    // Use the PORT environment variable when available (Render sets $PORT)
    port: Number(process.env.PORT) || 4173,
    // Explicitly empty, not omitted: `preview.proxy` falls back to
    // `server.proxy`, and a static host running `vite preview` in production
    // cannot reach DJANGO_ORIGIN, so every proxied request would 502.
    proxy: {},
  },
}))
