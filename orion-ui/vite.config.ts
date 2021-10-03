import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: [{ find: '@', replacement: resolve(__dirname, './src') }]
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
        @use '@prefecthq/miter-design/src/styles/abstracts/variables' as *;
        `
      }
    }
  },
  define: {
    'process.env': process.env
  }
})
