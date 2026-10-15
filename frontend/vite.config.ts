import path from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    resolve: { alias: { '@': path.resolve(__dirname, './src') } },
    server: {
      port: 5173,
      proxy: { '/api': { target: env.API_URL ?? 'http://localhost:8000', changeOrigin: true } },
    },
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 900,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('@mui/x-charts')) return 'charts';
            if (id.includes('@mui') || id.includes('@emotion')) return 'mui';
            if (id.includes('node_modules')) return 'vendor';
            return undefined;
          },
        },
      },
    },
  };
});
