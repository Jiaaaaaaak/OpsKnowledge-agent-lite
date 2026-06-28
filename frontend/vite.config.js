/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: false,
    // 單元測試只跑 src/ 下的 *.test.tsx；e2e/ 由 Playwright 跑，不能被 vitest 收進來。
    include: ['src/**/*.test.{ts,tsx}'],
    exclude: ['**/node_modules/**', 'e2e/**'],
  },
  server: {
    host: '0.0.0.0',
    port: 8501,
    // WSL2/Docker bind mount 的檔案事件不一定會傳進容器，改用輪詢確保 HMR 生效
    watch: { usePolling: true },
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 8501,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://backend:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})