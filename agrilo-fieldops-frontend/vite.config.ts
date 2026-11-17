import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/backend': { target: process.env.FIELDOPS_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true, rewrite: path => path.replace(/^\/backend/, '') } } },
  test: { environment: 'jsdom', setupFiles: ['./tests/setup.ts'], include: ['tests/**/*.test.{ts,tsx}'], restoreMocks: true, maxWorkers: 2, testTimeout: 10000 },
  build: { rollupOptions: { output: { manualChunks: { map: ['leaflet', 'react-leaflet', '@geoman-io/leaflet-geoman-free'], spatial: ['@turf/area', '@turf/bbox', '@turf/helpers', '@turf/intersect', '@turf/kinks'] } } } },
})
