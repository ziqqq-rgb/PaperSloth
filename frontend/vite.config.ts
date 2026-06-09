import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Forward /auth and /api to FastAPI backend
      '/auth': { target: 'http://localhost:8000', changeOrigin: true },
      '/api':  { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  resolve: {
     alias: {
       '@api':        path.resolve(__dirname, 'src/api'),
       '@store':      path.resolve(__dirname, 'src/store'),
       '@components': path.resolve(__dirname, 'src/components'),
       '@pages':      path.resolve(__dirname, 'src/pages'),
       '@utils':      path.resolve(__dirname, 'src/utils'),
     }
   },
})