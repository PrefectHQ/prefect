import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: process.env.PREFECT_UI_SERVE_BASE ?? '',
  resolve: {
    alias: [{ find: '@', replacement: resolve(__dirname, './src') }],
    dedupe: ['vue', 'vue-router'],
  },
  css: {
    devSourcemap: true,
  },
})
