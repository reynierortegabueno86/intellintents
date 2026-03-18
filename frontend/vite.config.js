import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/intellintents/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/intellintents/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/intellintents\/api/, '/intellintents/api')
      }
    }
  }
})
