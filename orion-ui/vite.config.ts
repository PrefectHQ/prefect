import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: process.env.ORION_UI_SERVE_BASE ?? '',
  resolve: {
    alias: [{ find: '@', replacement: resolve(__dirname, './src') }],
    dedupe: ['vue'],
  },
  css: {
    devSourcemap: true,
  },
})
