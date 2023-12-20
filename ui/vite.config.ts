import { resolve } from 'path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const baseFromEnv = process.env.PREFECT_UI_SERVE_BASE ?? process.env.PREFECT_UI_SERVE_BASE_REPLACE_PLACEHOLDER ?? ''
  const base = mode == 'development' ? '' : baseFromEnv
  return {
    plugins: [vue()],
    base,
    resolve: {
      alias: [{ find: '@', replacement: resolve(__dirname, './src') }],
      dedupe: ['vue', 'vue-router'],
    },
    css: {
      devSourcemap: true,
    },
  }
})
