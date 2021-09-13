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
        @use '@prefect/miter-design/src/styles/abstracts/variables' as *;
        @use "@/styles/main.scss" as *;
        `
      }
    }
  },
  define: {
    'process.env': process.env
  }
})
