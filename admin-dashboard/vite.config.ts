import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://unix:/home/terminal_ideas/cashflip/gunicorn.sock',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4174,
    host: '127.0.0.1',
    allowedHosts: [
      'demo.console.cashflip.amoano.com',
      'console.cashflip.amoano.com',
    ],
  },
  build: {
    outDir: 'dist',
  },
})
