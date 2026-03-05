import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8001'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        // Keep original host so FastAPI redirect Location stays browser-reachable
        // when a trailing-slash redirect happens.
        changeOrigin: false,
      },
    },
  },
})
