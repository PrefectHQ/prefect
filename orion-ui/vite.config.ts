import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  base: process.env['ORION_UI_SERVE_BASE'] || '',
  resolve: {
    alias: [{ find: '@', replacement: resolve(__dirname, './src') }]
  },
  css: {
    devSourcemap: true,
    preprocessorOptions: {
      scss: {
        charset: false,
        additionalData: `
        @use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
        `
      }
    }
  }
})
