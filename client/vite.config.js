import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,        // listen on all addresses (0.0.0.0), fixes some Windows/IDE cases
    port: 5173,
    strictPort: true,
  },
})
