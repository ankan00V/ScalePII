import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: process.env.SCALEPII_LOCAL_BUILD === '1'
    ? {
        alias: {
          '@appdeploy/client': fileURLToPath(new URL('./src/local-api.ts', import.meta.url)),
        },
      }
    : undefined,
});
