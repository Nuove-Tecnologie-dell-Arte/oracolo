import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // `npm run dev`: le chiamate /api vanno al backend (`backend.main serve`),
  // altrimenti Vite risponde con index.html e il frontend non trova i dati.
  server: {
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
});
