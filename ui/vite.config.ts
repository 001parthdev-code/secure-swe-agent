import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

// The operator token is used by the Vite dev server ONLY. Never expose it via VITE_*.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: false,
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq) => {
            const token = process.env.SWE_DEV_API_TOKEN;
            if (token) proxyReq.setHeader('X-Operator-Token', token);
          });
        },
      },
    },
  },
});
