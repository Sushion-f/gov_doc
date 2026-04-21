import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  base: '/document-chat/',
  plugins: [vue()],
  optimizeDeps: {
    include: [
      'tinymce/tinymce',
      'tinymce/themes/silver/theme',
      'tinymce/icons/default/icons',
      'tinymce/models/dom/model',
    ],
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 8080,
    proxy: {
      '/ucenter': {
        target: 'https://10.108.8.116:18085',
        changeOrigin: true,
        ws: true,
        secure: false,
      },
      '/bsp': {
        target: 'https://10.108.8.116:18085',
        changeOrigin: true,
        ws: true,
        secure: false,
      },
      // 与线上网关路径一致；本地开发时转发到分析服务
      '/police/analyse': {
        target: 'https://10.108.8.116:18090',
        changeOrigin: true,
        secure: false,
        rewrite: (path: any) => path.replace(/^\/police\/analyse/, '/ai-seat')
      },
      '/police/brain': {
        target: 'http://localhost:8088',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist/ai-police',
  },
});
