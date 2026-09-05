import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Base is relative so the built bundle works when Flask serves it from
// any mount path, not just the domain root.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // Lets `npm run dev` hit the Flask API on :5000 without a CORS
      // dance — same as production, where Flask serves both.
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});