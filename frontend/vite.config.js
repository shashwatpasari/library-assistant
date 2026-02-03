import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  plugins: [react()],
  root: '.',
  publicDir: 'public',
  server: {
    port: 3000,
    open: true
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        catalog: resolve(__dirname, 'catalog.html'),
        'book-details': resolve(__dirname, 'book-details.html'),
        'my-books': resolve(__dirname, 'my-books.html'),
        login: resolve(__dirname, 'login.html'),
        signup: resolve(__dirname, 'signup.html'),
        onboarding: resolve(__dirname, 'onboarding.html'),
        lists: resolve(__dirname, 'lists.html'),
        'reset-password': resolve(__dirname, 'reset-password.html')
      }
    }
  }
});

