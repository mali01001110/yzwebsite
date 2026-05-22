import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  preview: {
    // Allow the host Render reported as blocked
    allowedHosts: ['yannzakpa.space'],
    // Bind to all interfaces so Render can detect the open port
    host: '0.0.0.0',
    // Use the PORT environment variable when available (Render sets $PORT)
    port: Number(process.env.PORT) || 4173
  },
  // Optional: make local dev server behave similarly
  server: {
    host: true, // equivalent to 0.0.0.0
    port: Number(process.env.PORT) || 5173
  }
})